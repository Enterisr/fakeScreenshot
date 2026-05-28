"""Pydantic data models for the Fake News Screenshot Validator."""

from typing import Optional

from pydantic import BaseModel, field_validator


class ValidationResponse(BaseModel):
    """Response model for screenshot validation results.

    Validates: Requirements 5.1, 4.1, 2.5
    """

    is_real: bool
    confidence: float  # 0.0 to 1.0
    extracted_text: str
    sources: list[str]  # URLs of matching sources
    details: Optional[dict] = None

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_bounded(cls, v: float) -> float:
        """Confidence must be between 0.0 and 1.0 inclusive."""
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class OCRResult(BaseModel):
    """Result model for OCR text extraction.

    Validates: Requirements 2.5
    """

    full_text: str
    headline: str
    language: str  # detected primary language
    ocr_confidence: float  # OCR engine confidence

    @field_validator("ocr_confidence")
    @classmethod
    def ocr_confidence_must_be_bounded(cls, v: float) -> float:
        """OCR confidence must be between 0.0 and 1.0 inclusive."""
        if v < 0.0 or v > 1.0:
            raise ValueError("ocr_confidence must be between 0.0 and 1.0")
        return v


class SearchResult(BaseModel):
    """Model for a single web search result.

    Validates: Requirements 3.2
    """

    title: str
    url: str
    snippet: str
    date: Optional[str] = None
    source_name: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Title is required and must not be empty."""
        if not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        """URL is required and must not be empty."""
        if not v.strip():
            raise ValueError("url must not be empty")
        return v
