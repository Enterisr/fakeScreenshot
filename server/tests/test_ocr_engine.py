"""Unit tests for the OCR Engine.

Tests the OCREngine class with mocked EasyOCR to avoid requiring
the large model download during testing.
"""

import sys
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from server.models.schemas import OCRResult


def _make_image_bytes(width=100, height=100):
    """Create minimal valid PNG image bytes for testing."""
    img = Image.new("RGB", (width, height), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_ocr_engine_with_mock_reader():
    """Create an OCREngine instance without actually importing easyocr.

    Patches the easyocr import inside __init__ so we don't need the
    heavy dependency installed.
    """
    mock_easyocr = MagicMock()
    mock_reader = MagicMock()
    mock_easyocr.Reader.return_value = mock_reader

    with patch.dict(sys.modules, {"easyocr": mock_easyocr}):
        from server.engines.ocr_engine import OCREngine

        engine = OCREngine()

    return engine, mock_reader, mock_easyocr


class TestOCREngineInit:
    """Tests for OCREngine initialization."""

    def test_default_languages(self):
        """OCREngine initializes with Hebrew and English by default."""
        mock_easyocr = MagicMock()
        mock_easyocr.Reader.return_value = MagicMock()

        with patch.dict(sys.modules, {"easyocr": mock_easyocr}):
            from server.engines.ocr_engine import OCREngine

            engine = OCREngine()
            mock_easyocr.Reader.assert_called_once_with(["he", "en"], gpu=False)

    def test_custom_languages(self):
        """OCREngine can be initialized with custom languages."""
        mock_easyocr = MagicMock()
        mock_easyocr.Reader.return_value = MagicMock()

        with patch.dict(sys.modules, {"easyocr": mock_easyocr}):
            from server.engines.ocr_engine import OCREngine

            engine = OCREngine(languages=["en"])
            mock_easyocr.Reader.assert_called_once_with(["en"], gpu=False)


class TestExtractText:
    """Tests for the extract_text method."""

    def test_no_text_extracted(self):
        """When no text is extracted, returns empty result with 0.0 confidence."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = []

        result = engine.extract_text(_make_image_bytes())

        assert isinstance(result, OCRResult)
        assert result.full_text == ""
        assert result.headline == ""
        assert result.language == ""
        assert result.ocr_confidence == 0.0

    def test_single_text_block(self):
        """Extracts a single text block correctly."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = [
            ([[0, 0], [100, 0], [100, 30], [0, 30]], "Hello World", 0.95)
        ]

        result = engine.extract_text(_make_image_bytes())

        assert result.full_text == "Hello World"
        assert result.headline == "Hello World"
        assert result.language == "en"
        assert result.ocr_confidence == 0.95

    def test_multiple_text_blocks_headline_is_largest(self):
        """Headline is the text block with the largest bounding box area."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = [
            # Small text block (100 * 20 = 2000 area)
            ([[0, 50], [100, 50], [100, 70], [0, 70]], "Small text", 0.9),
            # Large text block (300 * 50 = 15000 area) - this is the headline
            ([[0, 0], [300, 0], [300, 50], [0, 50]], "Big Headline", 0.85),
            # Medium text block (150 * 25 = 3750 area)
            ([[0, 80], [150, 80], [150, 105], [0, 105]], "Medium text", 0.88),
        ]

        result = engine.extract_text(_make_image_bytes(400, 200))

        assert result.headline == "Big Headline"
        assert "Small text" in result.full_text
        assert "Big Headline" in result.full_text
        assert "Medium text" in result.full_text

    def test_confidence_is_average(self):
        """OCR confidence is the average of all block confidences."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = [
            ([[0, 0], [100, 0], [100, 30], [0, 30]], "Text A", 0.8),
            ([[0, 40], [100, 40], [100, 70], [0, 70]], "Text B", 0.6),
        ]

        result = engine.extract_text(_make_image_bytes())

        assert result.ocr_confidence == pytest.approx(0.7, abs=0.01)

    def test_hebrew_text_detected(self):
        """Hebrew text is detected and language is set to 'he'."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = [
            ([[0, 0], [200, 0], [200, 40], [0, 40]], "שלום עולם", 0.9)
        ]

        result = engine.extract_text(_make_image_bytes(300, 100))

        assert result.language == "he"
        assert result.full_text == "שלום עולם"


class TestExtractHeadline:
    """Tests for the extract_headline method."""

    def test_no_text_returns_empty(self):
        """When no text is found, returns empty string."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = []

        result = engine.extract_headline(_make_image_bytes())

        assert result == ""

    def test_returns_largest_bbox_text(self):
        """Returns the text from the largest bounding box."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        mock_reader.readtext.return_value = [
            ([[0, 0], [50, 0], [50, 10], [0, 10]], "tiny", 0.9),
            ([[0, 20], [400, 20], [400, 80], [0, 80]], "HEADLINE", 0.85),
        ]

        result = engine.extract_headline(_make_image_bytes(500, 200))

        assert result == "HEADLINE"


class TestDetectLanguage:
    """Tests for the _detect_language helper."""

    def test_empty_text(self):
        """Empty text returns empty language."""
        engine, _, _ = _create_ocr_engine_with_mock_reader()
        assert engine._detect_language("") == ""

    def test_english_text(self):
        """English text returns 'en'."""
        engine, _, _ = _create_ocr_engine_with_mock_reader()
        assert engine._detect_language("Hello World") == "en"

    def test_hebrew_text(self):
        """Hebrew text returns 'he'."""
        engine, _, _ = _create_ocr_engine_with_mock_reader()
        assert engine._detect_language("שלום עולם") == "he"

    def test_mixed_mostly_hebrew(self):
        """Mixed text with mostly Hebrew returns 'he'."""
        engine, _, _ = _create_ocr_engine_with_mock_reader()
        assert engine._detect_language("שלום Hello עולם") == "he"

    def test_numbers_only(self):
        """Text with only numbers defaults to 'en'."""
        engine, _, _ = _create_ocr_engine_with_mock_reader()
        assert engine._detect_language("12345") == "en"


class TestOCRError:
    """Tests for error handling in OCR processing."""

    def test_invalid_image_bytes(self):
        """Invalid image bytes result in empty OCR result."""
        engine, mock_reader, _ = _create_ocr_engine_with_mock_reader()
        # The PIL.Image.open will raise an exception for invalid bytes

        result = engine.extract_text(b"not an image")

        assert result.full_text == ""
        assert result.headline == ""
        assert result.ocr_confidence == 0.0
