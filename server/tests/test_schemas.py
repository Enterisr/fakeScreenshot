"""Unit tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from server.models.schemas import OCRResult, SearchResult, ValidationResponse


class TestValidationResponse:
    """Tests for ValidationResponse model."""

    def test_valid_response(self):
        resp = ValidationResponse(
            is_real=True,
            confidence=0.85,
            extracted_text="Breaking news headline",
            sources=["https://example.com/article"],
        )
        assert resp.is_real is True
        assert resp.confidence == 0.85
        assert resp.extracted_text == "Breaking news headline"
        assert resp.sources == ["https://example.com/article"]
        assert resp.details is None

    def test_confidence_at_bounds(self):
        resp_low = ValidationResponse(
            is_real=False, confidence=0.0, extracted_text="text", sources=[]
        )
        assert resp_low.confidence == 0.0

        resp_high = ValidationResponse(
            is_real=True, confidence=1.0, extracted_text="text", sources=[]
        )
        assert resp_high.confidence == 1.0

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError, match="confidence must be between"):
            ValidationResponse(
                is_real=False, confidence=-0.1, extracted_text="text", sources=[]
            )

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError, match="confidence must be between"):
            ValidationResponse(
                is_real=True, confidence=1.1, extracted_text="text", sources=[]
            )

    def test_optional_details(self):
        resp = ValidationResponse(
            is_real=False,
            confidence=0.3,
            extracted_text="some text",
            sources=[],
            details={"error": "Search service unavailable"},
        )
        assert resp.details == {"error": "Search service unavailable"}


class TestOCRResult:
    """Tests for OCRResult model."""

    def test_valid_ocr_result(self):
        result = OCRResult(
            full_text="Full extracted text",
            headline="Main Headline",
            language="he",
            ocr_confidence=0.92,
        )
        assert result.full_text == "Full extracted text"
        assert result.headline == "Main Headline"
        assert result.language == "he"
        assert result.ocr_confidence == 0.92

    def test_ocr_confidence_at_bounds(self):
        result_low = OCRResult(
            full_text="", headline="", language="en", ocr_confidence=0.0
        )
        assert result_low.ocr_confidence == 0.0

        result_high = OCRResult(
            full_text="text", headline="head", language="he", ocr_confidence=1.0
        )
        assert result_high.ocr_confidence == 1.0

    def test_ocr_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError, match="ocr_confidence must be between"):
            OCRResult(
                full_text="text", headline="head", language="en", ocr_confidence=-0.5
            )

    def test_ocr_confidence_above_one_raises(self):
        with pytest.raises(ValidationError, match="ocr_confidence must be between"):
            OCRResult(
                full_text="text", headline="head", language="en", ocr_confidence=1.5
            )


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_valid_search_result(self):
        result = SearchResult(
            title="News Article Title",
            url="https://news.example.com/article",
            snippet="A brief description of the article content.",
        )
        assert result.title == "News Article Title"
        assert result.url == "https://news.example.com/article"
        assert result.snippet == "A brief description of the article content."
        assert result.date is None
        assert result.source_name is None

    def test_search_result_with_optional_fields(self):
        result = SearchResult(
            title="Article",
            url="https://example.com",
            snippet="Snippet text",
            date="2025-01-15",
            source_name="Example News",
        )
        assert result.date == "2025-01-15"
        assert result.source_name == "Example News"

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError, match="title must not be empty"):
            SearchResult(
                title="", url="https://example.com", snippet="Some snippet"
            )

    def test_whitespace_title_raises(self):
        with pytest.raises(ValidationError, match="title must not be empty"):
            SearchResult(
                title="   ", url="https://example.com", snippet="Some snippet"
            )

    def test_empty_url_raises(self):
        with pytest.raises(ValidationError, match="url must not be empty"):
            SearchResult(title="Title", url="", snippet="Some snippet")

    def test_whitespace_url_raises(self):
        with pytest.raises(ValidationError, match="url must not be empty"):
            SearchResult(title="Title", url="  ", snippet="Some snippet")
