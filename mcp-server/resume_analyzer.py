import json
import re
from llm_service import LLMService

def analyze_resume(resume_text: str, job_description: str) -> dict:
    """
    Analyze a resume against a job description.
    """
    if not resume_text or not resume_text.strip():
        return {"error": "'resume_text' cannot be empty."}
    if not job_description or not job_description.strip():
        return {"error": "'job_description' cannot be empty."}

    system_prompt = (
        "You are a senior technical recruiter. "
        "Analyze the resume against the job description and respond ONLY in this exact JSON format "
        "(no markdown, no extra text):\n"
        "{\n"
        '  "matching_skills": ["skill1", "skill2"],\n'
        '  "missing_skills": ["skill1", "skill2"],\n'
        '  "improvement_areas": ["Specific actionable suggestion 1"],\n'
        '  "overall_impression": "Summary of fit"\n'
        "}\n\n"
    )

    prompt = (
        f"RESUME:\n{resume_text.strip()}\n\n"
        f"JOB DESCRIPTION:\n{job_description.strip()}\n\n"
        "Provide the structured JSON analysis."
    )

    raw = LLMService.call_llm(prompt, system_prompt, temperature=0)

    try:
        cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
        return json.loads(cleaned)
    except Exception:
        return {
            "matching_skills": [],
            "missing_skills": [],
            "improvement_areas": [],
            "overall_impression": raw,
            "parse_error": True,
            "warning": "LLM returned malformed JSON.",
        }
