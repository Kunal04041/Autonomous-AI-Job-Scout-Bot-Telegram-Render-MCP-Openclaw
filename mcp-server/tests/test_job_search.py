import pytest
from unittest.mock import patch, MagicMock
import json

from job_search import job_search, _deduplicate


MOCK_JOB = {
    "job_title": "ML Engineer",
    "employer_name": "Acme Corp",
    "job_city": "Pune",
    "job_country": "IN",
    "job_description": "We need Python, FastAPI, and ML experience. " * 50,
    "job_apply_link": "https://example.com/apply",
    "job_posted_at_datetime_utc": "2026-04-01T10:00:00Z",
    "job_is_remote": False,
    "job_employment_type": "FULLTIME",
}


def _make_mock_response(jobs: list, status: int = 200):
    """Build a mock http.client response."""
    mock_res = MagicMock()
    mock_res.status = status
    mock_res.read.return_value = json.dumps({"data": jobs}).encode("utf-8")
    return mock_res


@patch("job_search.http.client.HTTPSConnection")
@patch("job_search.os.getenv", return_value="fake_key")
def test_job_search_returns_results(mock_getenv, mock_conn_class):
    mock_conn = MagicMock()
    mock_conn_class.return_value = mock_conn
    mock_conn.getresponse.return_value = _make_mock_response([MOCK_JOB, MOCK_JOB])

    results = job_search("ML Engineer", "Pune, India", num_results=5)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["title"] == "ML Engineer"
    assert results[0]["company"] == "Acme Corp"


@patch("job_search.http.client.HTTPSConnection")
@patch("job_search.os.getenv", return_value="fake_key")
def test_description_truncated_at_2000(mock_getenv, mock_conn_class):
    long_job = dict(MOCK_JOB)
    long_job["job_description"] = "x" * 3000

    mock_conn = MagicMock()
    mock_conn_class.return_value = mock_conn
    mock_conn.getresponse.return_value = _make_mock_response([long_job])

    results = job_search("ML Engineer", "Pune, India")
    assert len(results[0]["description"]) <= 2003  # 2000 + "..."


@patch("job_search.os.getenv", return_value="")
def test_missing_api_key(mock_getenv):
    result = job_search("ML Engineer", "Pune")
    assert "error" in result[0]
    assert "JSEARCH_API_KEY" in result[0]["error"]


def test_empty_role_returns_error():
    result = job_search("", "Pune")
    assert "error" in result[0]


def test_empty_location_returns_error():
    result = job_search("ML Engineer", "")
    assert "error" in result[0]


@patch("job_search.http.client.HTTPSConnection")
@patch("job_search.os.getenv", return_value="fake_key")
def test_deduplication(mock_getenv, mock_conn_class):
    duplicate_jobs = [MOCK_JOB, MOCK_JOB, MOCK_JOB]
    mock_conn = MagicMock()
    mock_conn_class.return_value = mock_conn
    mock_conn.getresponse.return_value = _make_mock_response(duplicate_jobs)

    results = job_search("ML Engineer", "Pune", num_results=10)
    assert len(results) == 1  # duplicates removed


def test_deduplicate_helper():
    jobs = [
        {"title": "Engineer", "company": "Acme"},
        {"title": "Engineer", "company": "Acme"},
        {"title": "Engineer", "company": "Other Co"},
    ]
    result = _deduplicate(jobs)
    assert len(result) == 2


@patch("job_search.http.client.HTTPSConnection")
@patch("job_search.os.getenv", return_value="fake_key")
def test_rate_limit_returns_error(mock_getenv, mock_conn_class):
    mock_conn = MagicMock()
    mock_conn_class.return_value = mock_conn
    mock_conn.getresponse.return_value = _make_mock_response([], status=429)

    results = job_search("ML Engineer", "Pune")
    assert "error" in results[0]
    assert "rate limit" in results[0]["error"].lower()


@patch("job_search.http.client.HTTPSConnection")
@patch("job_search.os.getenv", return_value="fake_key")
def test_no_results_returns_message(mock_getenv, mock_conn_class):
    mock_conn = MagicMock()
    mock_conn_class.return_value = mock_conn
    mock_conn.getresponse.return_value = _make_mock_response([])

    results = job_search("VeryObscureRole12345", "Mars")
    assert "message" in results[0]
