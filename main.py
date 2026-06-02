import re
import time
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel

app = FastAPI(title="Regex Tester API", version="1.0.0")

# Simple in-memory rate limiting
rate_limit_store = defaultdict(list)
RATE_LIMIT = 60  # requests per minute
RATE_KEY = "bt_api_key_123"  # Single shared key for simplicity

class RegexTestRequest(BaseModel):
    pattern: str
    text: str
    flags: list[str] = []

class RegexTestResponse(BaseModel):
    matches: list[str]
    match_count: int
    indices: list[dict]
    valid: bool
    error: str | None = None

class ExplainRequest(BaseModel):
    pattern: str

class ExplainResponse(BaseModel):
    explanation: str
    components: list[str]
    valid: bool
    error: str | None = None

def rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    key = f"{client_ip}:{RATE_KEY}"
    
    requests = rate_limit_store[key]
    requests.extend([t for t in requests if now - t < 60])
    
    if len(requests) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    requests.append(now)
    return True

def verify_key(api_key: str = ""):
    if api_key != RATE_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

def parse_flags(flag_list: list[str]) -> int:
    flag_map = {
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
        "x": re.VERBOSE,
        "a": re.ASCII,
        "l": re.LOCALE,
    }
    flags = 0
    for f in flag_list:
        f_lower = f.lower()
        if f_lower in flag_map:
            flags |= flag_map[f_lower]
    return flags

@app.get("/health")
def health():
    return {"status": "ok", "service": "regex-tester"}

@app.post("/test")
def test_regex(body: RegexTestRequest, _ratelimit: bool = Depends(rate_limit)):
    """Test a regex pattern against text and return matches."""
    if not body.pattern:
        raise HTTPException(status_code=400, detail="Pattern is required")
    if not body.text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        flags = parse_flags(body.flags)
        compiled = re.compile(body.pattern, flags)
        matches = compiled.findall(body.text)
        indices = [{"start": m.start(), "end": m.end(), "group": m.group()} 
                   for m in compiled.finditer(body.text)]
        
        return RegexTestResponse(
            matches=matches,
            match_count=len(matches),
            indices=indices,
            valid=True
        )
    except re.error as e:
        return RegexTestResponse(
            matches=[],
            match_count=0,
            indices=[],
            valid=False,
            error=str(e)
        )

@app.post("/explain")
def explain_regex(body: ExplainRequest, _ratelimit: bool = Depends(rate_limit)):
    """Explain what a regex pattern does."""
    if not body.pattern:
        raise HTTPException(status_code=400, detail="Pattern is required")
    
    explanation_parts = []
    components = []
    
    try:
        # Parse the pattern for explanation
        explanation = f"Pattern: {body.pattern}"
        
        # Extract components
        tokens = re.findall(r'\\[.+?\\]|\\w+|\\W', body.pattern)
        for token in tokens:
            if token.startswith('\\'):
                if token == '\\d':
                    components.append("any digit (0-9)")
                elif token == '\\w':
                    components.append("any word character (a-z, A-Z, 0-9, _)")
                elif token == '\\s':
                    components.append("any whitespace")
                elif token == '\\.':
                    components.append("any character")
                elif token == '\\b':
                    components.append("word boundary")
                elif token == '\\^':
                    components.append("start of string anchor")
                elif token == '\\$':
                    components.append("end of string anchor")
                elif len(token) > 1 and token[1] in '?*+':
                    components.append(f"quantifier {token[1]}")
                elif token.startswith('\\('):
                    components.append("capturing group")
            elif token.isalnum():
                components.append(f"literal '{token}'")
            elif token in '.*+?^$[]{}|()':
                components.append(f"quantifier '{token}'")
        
        explanation_parts.append(explanation)
        explanation_parts.append(f"\nComponents: {', '.join(components) if components else 'No special components found'}")
        
        return ExplainResponse(
            explanation="\n".join(explanation_parts),
            components=components,
            valid=True
        )
    except Exception as e:
        return ExplainResponse(
            explanation="",
            components=[],
            valid=False,
            error=str(e)
        )

@app.post("/validate")
def validate_regex(body: ExplainRequest, _ratelimit: bool = Depends(rate_limit)):
    """Check if a regex pattern is valid."""
    if not body.pattern:
        raise HTTPException(status_code=400, detail="Pattern is required")
    
    try:
        re.compile(body.pattern)
        return {"valid": True, "pattern": body.pattern}
    except re.error as e:
        return {"valid": False, "pattern": body.pattern, "error": str(e)}

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass