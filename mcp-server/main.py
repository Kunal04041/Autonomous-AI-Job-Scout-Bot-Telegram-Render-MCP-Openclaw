import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from job_search import job_search as _job_search
from resume_analyzer import analyze_resume as _analyze_resume
from fit_score import get_job_fit_score as _get_fit_score

load_dotenv()


def _has_any_llm_provider_keys() -> bool:
    """Check that at least one LLM provider key is configured."""
    checks = [
        ("GEMINI_API_KEYS",     "GEMINI_API_KEY"),
        ("GITHUB_TOKENS",       "GITHUB_TOKEN"),
        ("CEREBRAS_API_KEYS",   "CEREBRAS_API_KEY"),
        ("GROQ_API_KEYS",       "GROQ_API_KEY"),
        ("SAMBANOVA_API_KEYS",  "SAMBANOVA_API_KEY"),
        ("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"),
    ]
    for multi, single in checks:
        if os.getenv(single, "").strip():
            return True
        value = os.getenv(multi, "").strip()
        if value and any(p.strip() for p in value.split(",")):
            return True
    return False


# ── Startup env validation ────────────────────────────────────────────────────
if not os.getenv("JSEARCH_API_KEY", "").strip():
    raise EnvironmentError(
        "Missing required environment variable: JSEARCH_API_KEY. "
        "Copy .env.example -> .env and fill in your keys."
    )

if not _has_any_llm_provider_keys():
    raise EnvironmentError(
        "No LLM API keys found. Set at least one of: "
        "GEMINI_API_KEY(S), GITHUB_TOKEN(S), CEREBRAS_API_KEY(S), "
        "GROQ_API_KEY(S), SAMBANOVA_API_KEY(S), OPENROUTER_API_KEY(S)."
    )

mcp = FastMCP("JobScoutServer")


@mcp.tool()
def job_search(
    role: str,
    location: str,
    num_results: int = 5,
    date_posted: str = "week",
    employment_type: str = None,
    remote_only: bool = False,
    page: int = 1,
) -> list:
    """
    Search for jobs by role and location using JSearch API (LinkedIn/Indeed/Glassdoor).

    Args:
        role:            Job title e.g. 'ML Engineer'
        location:        City/region e.g. 'Pune, India'
        num_results:     Number of results to return (1-10, default 5)
        date_posted:     'today' | 'week' | 'month' | 'all' (default 'week')
        employment_type: 'FULLTIME' | 'PARTTIME' | 'CONTRACT' | 'INTERN' (optional)
        remote_only:     True to return remote jobs only (default False)
        page:            Page number for pagination (default 1)
    """
    return _job_search(role, location, num_results, date_posted, employment_type, remote_only, page)


@mcp.tool()
def analyze_resume(resume_text: str, job_description: str) -> dict:
    """
    Analyze a resume against a job description.
    Returns matching skills, missing skills, improvement areas, and overall impression.
    """
    return _analyze_resume(resume_text, job_description)


@mcp.tool()
def get_job_fit_score(resume_text: str, job_description: str) -> dict:
    """
    Calculate a fit score (0-100) between a resume and a job description.
    Returns score, reason, verdict, matching_keywords, and missing_keywords.
    """
    return _get_fit_score(resume_text, job_description)


if __name__ == "__main__":
    print("[JobScoutServer] Starting MCP server...")
    print("[JobScoutServer] Registered tools: job_search, analyze_resume, get_job_fit_score")
    mcp.run()
