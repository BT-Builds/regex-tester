import re
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(title="Regex Tester API", version="1.0.0")

# Rate limiting storage (simple in-memory)
rate_limit_store = {}

def check_rate_limit(api_key: str = Header(None, alias="X-API-Key")):
    """Simple rate limiting: 100 requests per minute per API key"""
    import time
    if api_key is None:
        raise HTTPException(status_code=401, detail="API key required")
    current = time.time()
    if api_key not in rate_limit_store:
        rate_limit_store[api_key] = []
    rate_limit_store[api_key] = [t for t in rate_limit_store[api_key] if current - t < 60]
    if len(rate_limit_store[api_key]) >= 100:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    rate_limit_store[api_key].append(current)
    return api_key

class ValidateRequest(BaseModel):
    pattern: str = Field(..., description="The regex pattern to validate")
    flags: Optional[List[str]] = Field(default=[], description="Regex flags: i, m, s, x")

class TestRequest(BaseModel):
    pattern: str = Field(..., description="The regex pattern to test")
    text: str = Field(..., description="Text to match against")
    flags: Optional[List[str]] = Field(default=[], description="Regex flags: i, m, s, x")

class ExtractRequest(BaseModel):
    pattern: str = Field(..., description="The regex pattern to extract")
    text: str = Field(..., description="Text to extract from")
    flags: Optional[List[str]] = Field(default=[], description="Regex flags: i, m, s, x")

class ReplaceRequest(BaseModel):
    pattern: str = Field(..., description="The regex pattern to replace")
    text: str = Field(..., description="Text to process")
    replacement: str = Field(..., description="Replacement string")
    flags: Optional[List[str]] = Field(default=[], description="Regex flags: i, m, s, x")

def build_flags(flags_list: List[str]) -> int:
    """Convert flag strings to re module constants"""
    flag_map = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}
    flags = 0
    for f in flags_list:
        if f.lower() in flag_map:
            flags |= flag_map[f.lower()]
    return flags

@app.get("/health")
def health():
    return {"status": "ok", "service": "regex-tester"}

@app.post("/validate")
def validate_regex(req: ValidateRequest, _: str = Depends(check_rate_limit)):
    """Validate a regex pattern without testing against text"""
    try:
        flags = build_flags(req.flags)
        compiled = re.compile(req.pattern, flags)
        return {"valid": True, "pattern": req.pattern, "flags": req.flags}
    except re.error as e:
        return {"valid": False, "pattern": req.pattern, "error": str(e)}

@app.post("/test")
def test_regex(req: TestRequest, _: str = Depends(check_rate_limit)):
    """Test if pattern matches text"""
    flags = build_flags(req.flags)
    try:
        compiled = re.compile(req.pattern, flags)
        match = compiled.search(req.text)
        return {"matches": bool(match), "pattern": req.pattern, "text": req.text, "flags": req.flags}
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")

@app.post("/extract")
def extract_matches(req: ExtractRequest, _: str = Depends(check_rate_limit)):
    """Extract all matches from text"""
    flags = build_flags(req.flags)
    try:
        compiled = re.compile(req.pattern, flags)
        matches = compiled.findall(req.text)
        return {"matches": matches, "count": len(matches), "pattern": req.pattern, "flags": req.flags}
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")

@app.post("/replace")
def replace_matches(req: ReplaceRequest, _: str = Depends(check_rate_limit)):
    """Replace matches in text"""
    flags = build_flags(req.flags)
    try:
        compiled = re.compile(req.pattern, flags)
        result = compiled.sub(req.replacement, req.text)
        return {"original": req.text, "result": result, "pattern": req.pattern, "replacement": req.replacement, "flags": req.flags}
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")

@app.get("/explain/{pattern:path}")
def explain_pattern(pattern: str, _: str = Depends(check_rate_limit)):
    """Get explanation of regex pattern (basic analysis)"""
    explanations = []
    explanation_map = {
        r"\d": "Matches any digit (0-9)",
        r"\w": "Matches any word character (a-z, A-Z, 0-9, _)",
        r"\s": "Matches any whitespace character",
        r".*": "Matches any character 0 or more times",
        r".+": "Matches any character 1 or more times",
        r"\.": "Matches literal dot character",
        r"\b": "Word boundary",
        r"\B": "Non-word boundary",
        r"^": "Start of string",
        r"$": "End of string",
        r"[]": "Character class",
        r"()": "Capturing group",
        r"\|": "Alternation (or)",
        r"*?": "Non-greedy 0 or more",
        r"+?": "Non-greedy 1 or more",
    }
    for key, desc in explanation_map.items():
        if key in pattern:
            explanations.append(desc)
    return {"pattern": pattern, "explanations": explanations if explanations else ["No common patterns detected - pattern uses standard regex syntax"]}

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass