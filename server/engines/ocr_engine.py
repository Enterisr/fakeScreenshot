"""OCR Engine for extracting text from news screenshot images.

Uses EasyOCR with English language support.
Validates: Requirements 2.1, 2.3, 2.4, 2.5
"""

import logging
from io import BytesIO

import numpy as np
from PIL import Image

from server.models.schemas import OCRResult

logger = logging.getLogger(__name__)


class OCREngine:
    """OCR engine that extracts text from images using EasyOCR.

    The EasyOCR reader is initialized once and reused across requests
    to avoid repeated model loading.
    """

    def __init__(self, languages: list[str] = None):
        """Initialize EasyOCR reader with specified languages.

        Args:
            languages: List of language codes for EasyOCR.
                       Defaults to ["en"] (English).
        """
        import easyocr

        if languages is None:
            languages = ["en"]

        self._languages = languages
        logger.info("Initializing EasyOCR reader with languages: %s", languages)
        self._reader = easyocr.Reader(languages, gpu=False)
        logger.info("EasyOCR reader initialized successfully")

    def extract_text(self, image_bytes: bytes) -> OCRResult:
        """Extract all text from the image.

        Args:
            image_bytes: Raw bytes of the image file.

        Returns:
            OCRResult with full_text, headline, language, and ocr_confidence.
            If no text is extracted, returns empty result with 0.0 confidence.
        """
        results = self._run_ocr(image_bytes)

        if not results:
            return OCRResult(
                full_text="",
                headline="",
                language="",
                ocr_confidence=0.0,
            )

        texts = []
        confidences = []
        for bbox, text, confidence in results:
            texts.append(text)
            confidences.append(confidence)

        full_text = " ".join(texts)
        headline = self._find_headline(results)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            full_text=full_text,
            headline=headline,
            language="en",
            ocr_confidence=min(max(avg_confidence, 0.0), 1.0),
        )

    def extract_headline(self, image_bytes: bytes) -> str:
        """Extract the most prominent text (headline) from the image.

        Args:
            image_bytes: Raw bytes of the image file.

        Returns:
            The headline text string, or empty string if no text found.
        """
        results = self._run_ocr(image_bytes)
        if not results:
            return ""
        return self._find_headline(results)

    def _run_ocr(self, image_bytes: bytes) -> list:
        """Run EasyOCR on the image bytes."""
        try:
            image = Image.open(BytesIO(image_bytes))
            image_np = np.array(image)
            results = self._reader.readtext(image_np)
            return results
        except Exception as e:
            logger.error("OCR processing failed: %s", str(e))
            return []

    def _find_headline(self, results: list) -> str:
        """Find the most prominent text block by bounding box area."""
        if not results:
            return ""

        max_area = 0
        headline_text = ""

        for bbox, text, confidence in results:
            xs = [point[0] for point in bbox]
            ys = [point[1] for point in bbox]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if area > max_area:
                max_area = area
                headline_text = text

        return headline_text
