import json
import re
from llm_service import LLMService

def get_job_fit_score(resume_text: str, job_description: str) -> dict:
    """
    Calculate a fit score (0-100) between a resume and a job description.
    """
    if not resume_text or not resume_text.strip():
        return {"error": "'resume_text' cannot be empty."}
    if not job_description or not job_description.strip():
        return {"error": "'job_description' cannot be empty."}

    system_prompt = (
        "You are an AI hiring assistant. Score the resume against the job description. "
        "Respond ONLY with valid JSON:\n"
        "{\n"
        '  "score": <int 0-100>,\n'
        '  "reason": "summary string",\n'
        '  "matching_keywords": ["skill1"],\n'
        '  "missing_keywords": ["skill2"]\n'
        "}"
    )

    prompt = (
        f"RESUME:\n{resume_text.strip()}\n\n"
        f"JOB DESCRIPTION:\n{job_description.strip()}\n\n"
        "Score based on technical overlap and experience."
    )

    raw = LLMService.call_llm(prompt, system_prompt, temperature=0)

    try:
        cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
        parsed = json.loads(cleaned)
        score = int(parsed.get("score", 0))
        parse_error = False
    except Exception:
        match = re.search(r'"score"\s*:\s*(\d+)', raw)
        score = int(match.group(1)) if match else 0
        parsed = {"score": score, "reason": raw}
        parse_error = True

    if score >= 80: verdict = "Strong Match"
    elif score >= 60: verdict = "Good Match"
    elif score >= 40: verdict = "Partial Match"
    else: verdict = "Weak Match"

    result = {
        "score":             score,
        "reason":            parsed.get("reason", raw),
        "verdict":           verdict,
        "matching_keywords": parsed.get("matching_keywords", []),
        "missing_keywords":  parsed.get("missing_keywords", []),
    }
    if parse_error: 
        result["parse_error"] = True
    return result
