import pytest
from unittest.mock import patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fit_score import get_job_fit_score

SAMPLE_RESUME = """Kunal | Python Developer
Skills: Python, FastAPI, Docker, Qdrant, LLM integration, RAG pipelines
Experience: 1 year building chatbot backends with FastAPI and WebSocket."""

SAMPLE_JD = """ML Engineer — Python required. Experience with LLMs, RAG, and vector databases.
FastAPI or Flask backend experience preferred. Docker knowledge a plus."""


class TestFitScore:
    def test_empty_resume_returns_error(self):
        result = get_job_fit_score("", SAMPLE_JD)
        assert "error" in result

    def test_empty_jd_returns_error(self):
        result = get_job_fit_score(SAMPLE_RESUME, "")
        assert "error" in result

    @patch("fit_score.LLMService.call_llm")
    def test_valid_json_response(self, mock_llm):
        mock_llm.return_value = '{"score": 82, "reason": "Strong Python and LLM alignment."}'
        result = get_job_fit_score(SAMPLE_RESUME, SAMPLE_JD)
        assert result["score"] == 82
        assert result["verdict"] == "Strong Match"
        assert "reason" in result

    @patch("fit_score.LLMService.call_llm")
    def test_malformed_json_fallback(self, mock_llm):
        mock_llm.return_value = 'The score is approximately "score": 65 based on the resume.'
        result = get_job_fit_score(SAMPLE_RESUME, SAMPLE_JD)
        assert result["score"] == 65
        assert result["verdict"] == "Good Match"

    @patch("fit_score.LLMService.call_llm")
    def test_verdict_labels(self, mock_llm):
        for score, expected_verdict in [(85, "Strong Match"), (65, "Good Match"), (50, "Partial Match"), (20, "Weak Match")]:
            mock_llm.return_value = f'{{"score": {score}, "reason": "test"}}'
            result = get_job_fit_score(SAMPLE_RESUME, SAMPLE_JD)
            assert result["verdict"] == expected_verdict, f"Score {score} should be {expected_verdict}"

    @patch("fit_score.LLMService.call_llm")
    def test_markdown_fenced_json(self, mock_llm):
        mock_llm.return_value = '```json\n{"score": 75, "reason": "Good match."}\n```'
        result = get_job_fit_score(SAMPLE_RESUME, SAMPLE_JD)
        assert result["score"] == 75
