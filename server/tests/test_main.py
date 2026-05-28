"""Unit tests for the main FastAPI application endpoints.

Tests use httpx TestClient with mocked OCR and verification engines.
Validates: Requirements 1.1, 1.2, 1.3, 2.4, 3.3, 5.3, 5.4, 6.1
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.engines.verification_engine import VerificationResult
from server.models.schemas import OCRResult


@pytest.fixture
def client():
    """Create a test client with mocked engines (no real OCR initialization)."""
    mock_ocr = MagicMock()
    mock_verification = MagicMock()

    # Patch the engines before importing the app routes
    with patch("server.main.ocr_engine", mock_ocr), \
         patch("server.main.verification_engine", mock_verification):
        # Import app but override lifespan to avoid loading EasyOCR
        from server.main import app

        # Temporarily remove lifespan to avoid heavy initialization
        original_router = app.router
        original_lifespan = original_router.lifespan_context

        @asynccontextmanager
        async def mock_lifespan(app: FastAPI):
            yield

        original_router.lifespan_context = mock_lifespan
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c, mock_ocr, mock_verification
        finally:
            original_router.lifespan_context = original_lifespan


# --- Valid PNG header bytes for testing ---
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """GET /health returns 200 with status ok."""
        test_client, _, _ = client
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestValidateScreenshotEndpoint:
    """Tests for the /validate-screenshot endpoint."""

    def test_invalid_file_type_returns_400(self, client):
        """Uploading a non-image file returns HTTP 400."""
        test_client, _, _ = client
        # Random bytes that don't match any image magic bytes
        fake_file = b"This is not an image file at all"
        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("test.txt", fake_file, "text/plain")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid image format" in data["error"]

    def test_oversized_file_returns_413(self, client):
        """Uploading a file exceeding 10MB returns HTTP 413."""
        test_client, _, _ = client
        # Create a file larger than 10MB (10 * 1024 * 1024 + 1 bytes)
        oversized_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024 + 1)
        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("big.png", oversized_data, "image/png")},
        )
        assert response.status_code == 413
        data = response.json()
        assert "error" in data

    def test_successful_validation_flow(self, client):
        """Valid image with successful OCR and verification returns 200."""
        test_client, mock_ocr, mock_verification = client

        mock_ocr.extract_text.return_value = OCRResult(
            full_text="Breaking news headline",
            headline="Breaking news headline",
            language="en",
            ocr_confidence=0.9,
        )
        mock_verification.verify.return_value = VerificationResult(
            is_real=True,
            confidence=0.85,
            sources=["https://example.com/article"],
            search_results=[],
        )

        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("screenshot.png", PNG_HEADER, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_real"] is True
        assert data["confidence"] == 0.85
        assert data["extracted_text"] == "Breaking news headline"
        assert "https://example.com/article" in data["sources"]

    def test_ocr_no_text_returns_zero_confidence(self, client):
        """When OCR extracts no text, response has confidence 0.0."""
        test_client, mock_ocr, mock_verification = client

        mock_ocr.extract_text.return_value = OCRResult(
            full_text="",
            headline="",
            language="",
            ocr_confidence=0.0,
        )

        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("screenshot.png", PNG_HEADER, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_real"] is False
        assert data["confidence"] == 0.0
        assert data["extracted_text"] == ""
        assert data["details"] == {"error": "No text could be extracted"}
        # Verification should not be called when no text is extracted
        mock_verification.verify.assert_not_called()

    def test_search_failure_returns_zero_confidence(self, client):
        """When search fails, response has confidence 0.0 with error details."""
        test_client, mock_ocr, mock_verification = client

        mock_ocr.extract_text.return_value = OCRResult(
            full_text="Some extracted text",
            headline="Some extracted text",
            language="en",
            ocr_confidence=0.8,
        )
        mock_verification.verify.return_value = VerificationResult(
            is_real=False,
            confidence=0.0,
            sources=[],
            search_results=[],
            error="Search service unavailable",
        )

        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("screenshot.png", PNG_HEADER, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_real"] is False
        assert data["confidence"] == 0.0
        assert data["extracted_text"] == "Some extracted text"
        assert data["details"] == {"error": "Search service unavailable"}

    def test_response_structure_complete(self, client):
        """Successful response contains all required fields."""
        test_client, mock_ocr, mock_verification = client

        mock_ocr.extract_text.return_value = OCRResult(
            full_text="Test text",
            headline="Test text",
            language="en",
            ocr_confidence=0.7,
        )
        mock_verification.verify.return_value = VerificationResult(
            is_real=False,
            confidence=0.3,
            sources=[],
            search_results=[],
        )

        response = test_client.post(
            "/validate-screenshot",
            files={"file": ("screenshot.png", PNG_HEADER, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        # All required fields must be present
        assert "is_real" in data
        assert "confidence" in data
        assert "extracted_text" in data
        assert "sources" in data
        # Type checks
        assert isinstance(data["is_real"], bool)
        assert isinstance(data["confidence"], float)
        assert isinstance(data["extracted_text"], str)
        assert isinstance(data["sources"], list)
