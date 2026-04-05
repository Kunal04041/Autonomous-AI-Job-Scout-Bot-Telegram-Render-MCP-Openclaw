"""job_tracker.py
Maintains a persistent GOOGLE SHEET of all scraped jobs manually applied via JSearch
"""
import os
import json
from datetime import datetime
from pathlib import Path

# Tracking Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1VyHIhJWGLKbNoNiJroYNeS3at5xpMtD-ExYRUojrtLA"
# Default local key path
AUTH_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

COLUMNS = [
    "#", "Title", "Company", "Location",
    "Source", "Date Posted", "Date Discovered",
    "Status", "Applied", "Apply Link"
]

def _get_ws():
    """Authenticates gspread using Environment Variable OR local JSON."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Error: gspread/google-auth not installed.")
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        # 1. Try Environment Variable (For Render/Cloud)
        env_json = os.getenv("SERVICE_ACCOUNT_JSON")
        if env_json:
            try:
                creds_dict = json.loads(env_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                gc = gspread.authorize(creds)
            except json.JSONDecodeError:
                print("Error: SERVICE_ACCOUNT_JSON is not valid JSON.")
                return None
        
        # 2. Try Local File (For Laptop testing)
        elif Path(AUTH_FILE).exists():
            creds = Credentials.from_service_account_file(AUTH_FILE, scopes=scopes)
            gc = gspread.authorize(creds)
            
        else:
            print("Error: No Service Account credentials found.")
            return None

        # Connect to Sheet
        sh = gc.open_by_url(SHEET_URL)
        try:
            ws = sh.worksheet("All Jobs")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="All Jobs", rows=1000, cols=12)
            ws.append_row(COLUMNS)
            ws.format("A1:J1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)
        return ws

    except Exception as e:
        print(f"Google Sheet Auth Error: {e}")
        return None

def log_jobs(jobs: list, source: str = "JSearch-Cloud") -> int:
    """Append new jobs to the Google Sheet. Skips duplicates by URL."""
    if not jobs:
        return 0

    ws = _get_ws()
    if not ws:
        return 0
        
    # Get all current URLs from column J (index 10)
    all_values = ws.get_all_values()
    existing_urls = set()
    if len(all_values) > 1:
        for row in all_values[1:]:
            if len(row) > 9:
                existing_urls.add(str(row[9]).strip())

    added = 0
    today = datetime.now().strftime("%Y-%m-%d")
    rows_to_append = []

    for job in jobs:
        url = str(job.get("apply_link", "")).strip()
        if not url or not url.startswith("http"):
            continue
        if url in existing_urls:
            continue  # skip duplicate

        existing_urls.add(url)
        
        row = [
            len(all_values) + added,               # #
            job.get("title",    "N/A"),            # Title
            job.get("company",  "N/A"),            # Company
            job.get("location", "N/A"),            # Location
            source,                                # Source
            str(job.get("posted_at", "N/A")),      # Date Posted
            today,                                 # Date Discovered
            "Pending",                             # Status (Manual)
            "No",                                  # Applied (Manual)
            url,                                   # Apply Link
        ]
        rows_to_append.append(row)
        added += 1

    if rows_to_append:
        try:
            ws.append_rows(rows_to_append)
        except Exception:
            return 0

    return added
