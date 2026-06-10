import re
import os
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, field_validator
from mangum import Mangum

# ── API Key Auth (Upstash Redis) ───────────────────────────────────────────────
import os, time, json as _json
from urllib.request import Request as _Req, urlopen as _urlopen

_UPSTASH_URL   = os.environ.get('UPSTASH_REDIS_REST_URL', '')
_UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
_TIERS = {'free': 1000, 'starter': 25000, 'pro': 200000, 'demo': 50}

def _redis(cmd):
    url = f'{_UPSTASH_URL}/{cmd[0]}/' + '/'.join(str(x) for x in cmd[1:])
    req = _Req(url, headers={'Authorization': f'Bearer {_UPSTASH_TOKEN}'})
    try:
        return _json.loads(_urlopen(req, timeout=3).read()).get('result')
    except: return None

def verify_api_key(x_api_key: str = Header(default='free-demo-key')):
    if not _UPSTASH_URL:  # no Upstash configured, allow all (dev mode)
        return {'key': x_api_key, 'tier': 'free'}
    tier = 'demo'
    if x_api_key != 'free-demo-key':
        raw = _redis(['GET', f'key:{x_api_key}'])
        if not raw:
            raise HTTPException(401, 'Invalid API key. Get one at btbuilds.lemonsqueezy.com')
        data = _json.loads(raw)
        if not data.get('active', True):
            raise HTTPException(401, 'API key revoked')
        tier = data.get('tier', 'free')
    month = time.strftime('%Y-%m')
    used = int(_redis(['INCR', f'usage:{x_api_key}:{month}']) or 1)
    if used == 1: _redis(['EXPIRE', f'usage:{x_api_key}:{month}', 2678400])
    limit = _TIERS.get(tier, 1000)
    if used > limit:
        raise HTTPException(429, f'Monthly limit reached ({limit:,}/mo). Upgrade at btbuilds.lemonsqueezy.com')
    return {'key': x_api_key, 'tier': tier, 'used': used}


app = FastAPI(title="Regex Tester API", version="1.0.0")

# Rate limiting storage
rate_limits: dict = {}

# API Key auth
API_KEY = os.getenv("API_KEY", "demo-key-change-me")


def check_rate_limit(api_key: str = None):
    """Simple in-memory rate limiting: 100 requests per minute per key"""
    if api_key is None:
        api_key = "anonymous"
    
    current_time = time.time()
    minute_ago = current_time - 60
    
    # Clean old entries
    if api_key in rate_limits:
        rate_limits[api_key] = [t for t in rate_limits[api_key] if t > minute_ago]
        if len(rate_limits[api_key]) >= 100:
            raise HTTPException(status_code=429, detail="Rate limit exceeded: 100 requests per minute")
    
    rate_limits.setdefault(api_key, []).append(current_time)
    return api_key


def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    check_rate_limit(x_api_key)
    return x_api_key


# Request models
class RegexTestRequest(BaseModel):
    pattern: str
    text: str
    flags: Optional[str] = ""


class RegexValidateRequest(BaseModel):
    pattern: str


# Response models
class RegexTestResponse(BaseModel):
    pattern: str
    text: str
    matches: List[str]
    match_count: int
    groups: List[List[str]]
    matched_spans: List[List[List[int]]]


class RegexExplainResponse(BaseModel):
    pattern: str
    explanation: List[dict]
    syntax_valid: bool


class RegexValidateResponse(BaseModel):
    pattern: str
    valid: bool
    error: Optional[str] = None


# Common regex patterns
COMMON_PATTERNS = [
    {"name": "Email", "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "description": "Matches most email addresses"},
    {"name": "URL", "pattern": r"https?://[^\s/$.?#].[^\s]*", "description": "Matches HTTP/HTTPS URLs"},
    {"name": "Phone (US)", "pattern": r"\+1?\s*\(?(\d{3})\)?[\s-]*(\d{3})[\s-]*(\d{4})", "description": "Matches US phone numbers"},
    {"name": "IP Address", "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", "description": "Matches IPv4 addresses"},
    {"name": "Credit Card", "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "description": "Matches credit card numbers"},
    {"name": "Date (YYYY-MM-DD)", "pattern": r"\d{4}-\d{2}-\d{2}", "description": "Matches ISO date format"},
    {"name": "Hex Color", "pattern": r"#[a-fA-F0-9]{6}", "description": "Matches hex color codes"},
    {"name": "UUID", "pattern": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "description": "Matches UUIDs"},
    {"name": "HTML Tag", "pattern": r"<\/?[a-zA-Z][^\s\/]*(\s[^>]*)?>", "description": "Matches opening and closing HTML tags"},
    {"name": "Slugs", "pattern": r"[a-z0-9]+(?:-[a-z0-9]+)*", "description": "Matches URL-friendly slugs"},
]


def parse_flags(flags_str: str) -> int:
    """Convert flag string to re module flags"""
    flag_map = {
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
        "x": re.VERBOSE,
        "l": re.LOCALE,
        "u": re.UNICODE,
    }
    result = 0
    for flag in flags_str.lower():
        if flag in flag_map:
            result |= flag_map[flag]
    return result


def explain_pattern(pattern: str) -> List[dict]:
    """Explain regex components"""
    explanation = []
    i = 0
    try:
        # Basic explanation of common patterns
        tokens = [
            (r'\\d', 'digit', 'matches any digit 0-9'),
            (r'\\w', 'word', 'matches any word character a-z, A-Z, 0-9, _'),
            (r'\\s', 'whitespace', 'matches any whitespace character'),
            (r'\\b', 'boundary', 'matches word boundary'),
            (r'.', 'any', 'matches any character except newline'),
            (r'*', 'zero-or-more', 'matches 0 or more of previous'),
            (r'+', 'one-or-more', 'matches 1 or more of previous'),
            (r'?', 'optional', 'matches 0 or 1 of previous'),
            (r'^', 'start', 'matches start of string'),
            (r'$', 'end', 'matches end of string'),
            (r'[]', 'character-class', 'matches any char in brackets'),
            (r'()', 'group', 'capturing group'),
            (r'\\d{4}', 'quantifier', 'matches exactly 4 digits'),
            (r'\\d{4,}', 'quantifier', 'matches 4 or more digits'),
            (r'\\d{4,8}', 'quantifier-range', 'matches 4 to 8 digits'),
        ]
        
        for token, name, desc in tokens:
            if token in pattern:
                explanation.append({"token": token, "name": name, "description": desc, "matches": re.findall(token, pattern)})
        
        if not explanation:
            explanation.append({"token": pattern, "name": "custom", "description": "Custom regex pattern"})
    except Exception:
        explanation.append({"token": pattern, "name": "error", "description": "Could not parse pattern"})
    
    return explanation


@app.get("/health")
async def health():
    """Health check endpoint - no auth required"""
    return {"status": "ok", "service": "regex-tester"}


@app.post("/test")
async def test_regex(request: RegexTestRequest, api_key: str = Depends(verify_api_key)):
    """Test a regex pattern against text"""
    try:
        flags = parse_flags(request.flags)
        regex = re.compile(request.pattern, flags)
        matches = regex.findall(request.text)
        
        # Get match spans and groups
        matched_spans = []
        groups_list = []
        for match in regex.finditer(request.text):
            matched_spans.append([list(match.span())])
            groups_list.append(list(match.groups()))
        
        return RegexTestResponse(
            pattern=request.pattern,
            text=request.text,
            matches=matches,
            match_count=len(matches),
            groups=groups_list,
            matched_spans=matched_spans
        )
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")

@app.post("/bulk/test")
async def bulk_test_regex(requests: List[RegexTestRequest], api_key: str = Depends(verify_api_key)):
    """Test multiple regex patterns against text in bulk"""
    results = []
    successful = 0
    for req in requests:
        try:
            flags = parse_flags(req.flags)
            regex = re.compile(req.pattern, flags)
            matches = regex.findall(req.text)
            matched_spans = []
            groups_list = []
            for match in regex.finditer(req.text):
                matched_spans.append([list(match.span())])
                groups_list.append(list(match.groups()))
            results.append({
                "input": {"pattern": req.pattern, "text": req.text, "flags": req.flags},
                "output": {"matches": matches, "match_count": len(matches), "groups": groups_list, "matched_spans": matched_spans},
                "error": None
            })
            successful += 1
        except re.error as e:
            results.append({
                "input": {"pattern": req.pattern, "text": req.text, "flags": req.flags},
                "output": None,
                "error": str(e)
            })
    return {"results": results, "total": len(results), "successful": successful}


@app.post("/validate")
async def validate_regex(request: RegexValidateRequest, api_key: str = Depends(verify_api_key)):
    """Validate regex syntax"""
    try:
        re.compile(request.pattern)
        return RegexValidateResponse(pattern=request.pattern, valid=True)
    except re.error as e:
        return RegexValidateResponse(pattern=request.pattern, valid=False, error=str(e))

@app.post("/bulk/validate")
async def bulk_validate_regex(requests: List[RegexValidateRequest], api_key: str = Depends(verify_api_key)):
    """Validate multiple regex patterns in bulk"""
    results = []
    successful = 0
    for req in requests:
        try:
            re.compile(req.pattern)
            results.append({"input": {"pattern": req.pattern}, "output": {"valid": True}, "error": None})
            successful += 1
        except re.error as e:
            results.append({"input": {"pattern": req.pattern}, "output": {"valid": False}, "error": str(e)})
    return {"results": results, "total": len(results), "successful": successful}


@app.post("/explain")
async def explain_regex(request: RegexValidateRequest, api_key: str = Depends(verify_api_key)):
    """Explain regex components"""
    valid = True
    error = None
    try:
        re.compile(request.pattern)
    except re.error as e:
        valid = False
        error = str(e)
    
    return RegexExplainResponse(
        pattern=request.pattern,
        explanation=explain_pattern(request.pattern),
        syntax_valid=valid
    )

@app.post("/bulk/explain")
async def bulk_explain_regex(requests: List[RegexValidateRequest], api_key: str = Depends(verify_api_key)):
    """Explain multiple regex patterns in bulk"""
    results = []
    successful = 0
    for req in requests:
        try:
            syntax_valid = bool(re.compile(req.pattern))
            results.append({
                "input": {"pattern": req.pattern},
                "output": {"syntax_valid": syntax_valid, "explanation": explain_pattern(req.pattern)},
                "error": None
            })
            successful += 1
        except re.error as e:
            results.append({
                "input": {"pattern": req.pattern},
                "output": {"syntax_valid": False, "explanation": []},
                "error": str(e)
            })
    return {"results": results, "total": len(results), "successful": successful}


@app.get("/examples")
async def get_examples():
    """Get common regex patterns with examples - no auth required"""
    return {"patterns": COMMON_PATTERNS}


# Handler for Vercel
handler = Mangum(app)