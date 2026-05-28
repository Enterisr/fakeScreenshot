"""Unit tests for the image validation module.

Tests magic bytes checking and file size validation.
"""

import pytest

from server.utils.image_validator import (
    MAX_FILE_SIZE_BYTES,
    get_image_format,
    validate_file_size,
    validate_image,
    validate_image_format,
)

# --- Magic byte samples for supported formats ---

# Minimal PNG header (8 bytes magic + IHDR chunk start)
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

# Minimal JPEG header (starts with FF D8 FF)
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20

# Minimal WEBP header: RIFF + 4 bytes size + WEBP
WEBP_HEADER = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20


class TestMagicBytesDetection:
    """Tests for magic bytes format detection."""

    def test_detects_png(self):
        assert get_image_format(PNG_HEADER) == "png"

    def test_detects_jpeg(self):
        assert get_image_format(JPEG_HEADER) == "jpg"

    def test_detects_webp(self):
        assert get_image_format(WEBP_HEADER) == "webp"

    def test_rejects_empty_data(self):
        assert get_image_format(b"") is None

    def test_rejects_too_short_data(self):
        assert get_image_format(b"\x89PN") is None

    def test_rejects_random_bytes(self):
        assert get_image_format(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08") is None

    def test_rejects_text_file(self):
        assert get_image_format(b"Hello, this is a text file.") is None

    def test_rejects_pdf(self):
        assert get_image_format(b"%PDF-1.4 some content here") is None

    def test_rejects_gif(self):
        # GIF is not a supported format
        assert get_image_format(b"GIF89a" + b"\x00" * 20) is None

    def test_rejects_riff_non_webp(self):
        # RIFF header but not WEBP (e.g., AVI file)
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"AVI " + b"\x00" * 20
        assert get_image_format(data) is None


class TestValidateImageFormat:
    """Tests for validate_image_format function."""

    def test_valid_png(self):
        is_valid, error = validate_image_format(PNG_HEADER)
        assert is_valid is True
        assert error is None

    def test_valid_jpeg(self):
        is_valid, error = validate_image_format(JPEG_HEADER)
        assert is_valid is True
        assert error is None

    def test_valid_webp(self):
        is_valid, error = validate_image_format(WEBP_HEADER)
        assert is_valid is True
        assert error is None

    def test_invalid_format_returns_error(self):
        is_valid, error = validate_image_format(b"not an image at all")
        assert is_valid is False
        assert "Invalid image format" in error
        assert "PNG" in error
        assert "JPG" in error
        assert "WEBP" in error


class TestValidateFileSize:
    """Tests for file size validation."""

    def test_small_file_is_valid(self):
        data = b"\x00" * 1024  # 1KB
        is_valid, error = validate_file_size(data)
        assert is_valid is True
        assert error is None

    def test_exactly_10mb_is_valid(self):
        data = b"\x00" * MAX_FILE_SIZE_BYTES
        is_valid, error = validate_file_size(data)
        assert is_valid is True
        assert error is None

    def test_over_10mb_is_invalid(self):
        data = b"\x00" * (MAX_FILE_SIZE_BYTES + 1)
        is_valid, error = validate_file_size(data)
        assert is_valid is False
        assert "10MB" in error

    def test_empty_file_is_valid_size(self):
        is_valid, error = validate_file_size(b"")
        assert is_valid is True
        assert error is None


class TestValidateImage:
    """Tests for the combined validate_image function."""

    def test_valid_png_passes(self):
        is_valid, error, status = validate_image(PNG_HEADER)
        assert is_valid is True
        assert error is None
        assert status is None

    def test_valid_jpeg_passes(self):
        is_valid, error, status = validate_image(JPEG_HEADER)
        assert is_valid is True
        assert error is None
        assert status is None

    def test_valid_webp_passes(self):
        is_valid, error, status = validate_image(WEBP_HEADER)
        assert is_valid is True
        assert error is None
        assert status is None

    def test_invalid_format_returns_400(self):
        is_valid, error, status = validate_image(b"not an image")
        assert is_valid is False
        assert status == 400
        assert "Invalid image format" in error

    def test_oversized_file_returns_413(self):
        # Create oversized PNG (valid magic bytes but too large)
        data = PNG_HEADER + b"\x00" * MAX_FILE_SIZE_BYTES
        is_valid, error, status = validate_image(data)
        assert is_valid is False
        assert status == 413
        assert "10MB" in error

    def test_size_check_happens_before_format_check(self):
        # Even invalid format data that's too large should get 413
        data = b"\x00" * (MAX_FILE_SIZE_BYTES + 1)
        is_valid, error, status = validate_image(data)
        assert is_valid is False
        assert status == 413
