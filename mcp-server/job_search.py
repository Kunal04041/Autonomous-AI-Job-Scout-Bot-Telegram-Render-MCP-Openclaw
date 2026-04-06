import json
import re
import os
import http.client
from dotenv import load_dotenv

load_dotenv()

def _deduplicate(jobs: list) -> list:
    """Remove duplicate jobs by (title, company) pair."""
    seen = set()
    unique = []
    for job in jobs:
        key = (job.get("title", "").lower().strip(), job.get("company", "").lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique

def job_search(
    role: str,
    location: str,
    num_results: int = 5,
    date_posted: str = "month",
    employment_type: str = None,
    remote_only: bool = False,
    page: int = 1,
) -> list:
    """
    Search for jobs using JSearch API.
    """
    if not role or not role.strip():
        return [{"error": "'role' parameter cannot be empty."}]
    if not location or not location.strip():
        return [{"error": "'location' parameter cannot be empty."}]

    num_results = min(max(1, num_results), 10)
    valid_date_posted = {"today", "week", "month", "all"}
    if date_posted not in valid_date_posted:
        date_posted = "week"

    query = f"{role.strip()} in {location.strip()}"
    if remote_only:
        query += " remote"

    import urllib.parse
    encoded_query = urllib.parse.quote(query)

    path = (
        f"/search?query={encoded_query}"
        f"&page={page}"
        f"&num_pages=1"
        f"&date_posted={date_posted}"
    )
    if employment_type:
        path += f"&employment_types={employment_type.upper()}"
    if remote_only:
        path += "&remote_jobs_only=true"

    # API Key Fallback Strategy
    api_keys = [
        os.getenv("JSEARCH_API_KEY"),
        os.getenv("JSEARCH_API_KEY1"),
    ]
    api_keys = [k for k in api_keys if k]

    if not api_keys:
        return [{"error": "No JSEARCH_API_KEY found"}]

    data = None
    last_error = None

    for api_key in api_keys:
        try:
            conn = http.client.HTTPSConnection("jsearch.p.rapidapi.com", timeout=15)
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com",
                "Content-Type": "application/json",
            }
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            raw = res.read().decode("utf-8")
            conn.close()

            if res.status == 200:
                data = json.loads(raw)
                break
            elif res.status == 429:
                last_error = f"Rate limit (429) for key {api_key[:5]}"
                continue
            else:
                last_error = f"API error {res.status}"
                continue
        except Exception as e:
            last_error = str(e)
            continue

    if not data:
        return [{"error": f"All API keys failed. Last error: {last_error}"}]

    jobs_raw = data.get("data", [])
    if not jobs_raw:
        return [{"message": "No jobs found."}]

    results = []
    for j in jobs_raw:
        description = j.get("job_description", "") or ""
        if len(description) > 300:
            description = description[:300] + "..."

        apply_link = (
            j.get("job_apply_link")
            or j.get("job_google_link")
            or "N/A"
        )

        results.append({
            "title":       j.get("job_title", "N/A"),
            "company":     j.get("employer_name", "N/A"),
            "location":    j.get("job_city", "") + ", " + j.get("job_country", "") if j.get("job_city") else j.get("job_country", location),
            "description": description,
            "apply_link":  apply_link,
            "posted_at":   j.get("job_posted_at_datetime_utc", "N/A"),
            "remote":      j.get("job_is_remote", False),
            "employment_type": j.get("job_employment_type", "N/A"),
        })

    # Sort by posted_at (most recent first)
    results = _deduplicate(results)
    # Handle cases where posted_at might be 'N/A'
    results.sort(key=lambda x: x.get("posted_at", "") or "", reverse=True)
    return results[:num_results]
