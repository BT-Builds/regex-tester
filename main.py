import re
import time
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional
import mangum

app = FastAPI(title="Regex Tester API", version="1.0.0")

security = HTTPBearer()
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600
request_counts: dict = {}

def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    api_key = credentials.credentials
    if not api_key or len(api_key) < 10:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

def check_rate_limit(api_key: str):
    current_time = time.time()
    if api_key not in request_counts:
        request_counts[api_key] = []
    request_counts[api_key] = [t for t in request_counts[api_key] if current_time - t < RATE_LIMIT_WINDOW]
    if len(request_counts[api_key]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    request_counts[api_key].append(current_time)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "regex-tester"}

class RegexRequest(BaseModel):
    pattern: str
    test_string: Optional[str] = None
    flags: Optional[List[str]] = Field(default=[], description="Flags: i, m, s, x, a, l, u")

FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
    "a": re.ASCII,
    "l": re.LOCALE,
    "u": re.UNICODE,
}

def build_flags(flag_list: List[str]) -> int:
    flags = 0
    for flag in flag_list:
        if flag.lower() in FLAG_MAP:
            flags |= FLAG_MAP[flag.lower()]
    return flags

@app.post("/validate")
async def validate_regex(request: RegexRequest, api_key: str = Depends(get_api_key)):
    check_rate_limit(api_key)
    try:
        flags = build_flags(request.flags)
        compiled = re.compile(request.pattern, flags)
        if request.test_string:
            match_found = bool(compiled.search(request.test_string))
        else:
            match_found = None
        return {
            "valid": True,
            "matches": match_found,
            "pattern": request.pattern,
            "test_string": request.test_string,
        }
    except re.error as e:
        return {"valid": False, "error": str(e), "pattern": request.pattern}

@app.post("/match")
async def match_regex(request: RegexRequest, api_key: str = Depends(get_api_key)):
    check_rate_limit(api_key)
    try:
        flags = build_flags(request.flags)
        compiled = re.compile(request.pattern, flags)
        all_matches = []
        for m in compiled.finditer(request.test_string or ""):
            all_matches.append({
                "match": m.group(),
                "start": m.start(),
                "end": m.end(),
                "groups": list(m.groups()),
                "named_groups": m.groupdict() if m.groupdict() else None,
            })
        return {
            "valid": True,
            "matches": all_matches,
            "count": len(all_matches),
            "pattern": request.pattern,
        }
    except re.error as e:
        return {"valid": False, "error": str(e), "pattern": request.pattern}

class ExplainRequest(BaseModel):
    pattern: str

@app.post("/explain")
async def explain_regex(request: ExplainRequest, api_key: str = Depends(get_api_key)):
    check_rate_limit(api_key)
    pattern = request.pattern
    explanation = []
    try:
        re.compile(pattern)
    except re.error as e:
        return {"valid": False, "error": str(e), "pattern": pattern}
    special_chars = {
        ".": "Matches any character except newline",
        "^": "Matches start of string",
        "$": "Matches end of string",
        "*": "Matches 0 or more repetitions",
        "+": "Matches 1 or more repetitions",
        "?": "Matches 0 or 1 repetition",
        "{": "Matches exact repetitions (e.g., {2,4})",
        "|": "OR operator - matches either side",
        "(": "Capturing group",
        "[": "Character class - matches any inside",
        "\\": "Escape character for literals",
    }
    for char in set(pattern):
        if char in special_chars:
            explanation.append({"character": char, "description": special_chars[char]})
    quantifier_count = sum(1 for c in pattern if c in "*+?{")
    group_count = pattern.count("(") - pattern.count("\\(")
    character_class_count = pattern.count("[") - pattern.count("\\[")
    return {
        "valid": True,
        "pattern": pattern,
        "length": len(pattern),
        "quantifiers": quantifier_count,
        "groups": group_count,
        "character_classes": character_class_count,
        "explanation": explanation,
    }

class SubstituteRequest(BaseModel):
    pattern: str
    replacement: str
    test_string: str
    flags: Optional[List[str]] = Field(default=[])

@app.post("/substitute")
async def substitute_regex(request: SubstituteRequest, api_key: str = Depends(get_api_key)):
    check_rate_limit(api_key)
    try:
        compiled_flags = build_flags(request.flags)
        result = re.sub(request.pattern, request.replacement, request.test_string, flags=compiled_flags)
        return {
            "valid": True,
            "original": request.test_string,
            "result": result,
            "pattern": request.pattern,
            "replacement": request.replacement,
        }
    except re.error as e:
        return {"valid": False, "error": str(e), "pattern": request.pattern}

handler = mangum.Mangum(app)