"""Image validation utilities for uploaded files.

Validates image files by inspecting magic bytes (not file extension) and
enforcing a maximum file size limit.

Validates: Requirements 1.2, 1.3, 1.4, 8.1, 8.2
"""

# Maximum allowed file size: 10MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# Supported image formats and their magic byte signatures
MAGIC_BYTES = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "webp": [b"RIFF"],  # WEBP files start with RIFF....WEBP
}

SUPPORTED_FORMATS = ["PNG", "JPG", "JPEG", "WEBP"]


def _check_webp_signature(data: bytes) -> bool:
    """Check if data has a valid WEBP signature.

    WEBP files start with 'RIFF' followed by 4 bytes of file size,
    then 'WEBP'.
    """
    if len(data) < 12:
        return False
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _check_magic_bytes(data: bytes) -> str | None:
    """Check magic bytes of file data and return the detected format.

    Args:
        data: The raw file bytes to inspect.

    Returns:
        The detected format string (e.g., "png", "jpg", "webp") or None
        if the format is not supported.
    """
    if len(data) < 4:
        return None

    # Check WEBP first (needs special handling for RIFF....WEBP pattern)
    if _check_webp_signature(data):
        return "webp"

    # Check PNG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    # Check JPG/JPEG
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"

    return None


def validate_file_size(data: bytes) -> tuple[bool, str | None]:
    """Validate that the file does not exceed the maximum size limit.

    Args:
        data: The raw file bytes.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if len(data) > MAX_FILE_SIZE_BYTES:
        return False, f"Image too large. Maximum size: 10MB"
    return True, None


def validate_image_format(data: bytes) -> tuple[bool, str | None]:
    """Validate that the file is a supported image format by checking magic bytes.

    This inspects the actual file content (magic bytes), not the file extension,
    to prevent spoofed uploads.

    Args:
        data: The raw file bytes to inspect.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is None.
    """
    detected_format = _check_magic_bytes(data)
    if detected_format is None:
        return False, "Invalid image format. Supported: PNG, JPG, JPEG, WEBP"
    return True, None


def validate_image(data: bytes) -> tuple[bool, str | None, int | None]:
    """Validate an uploaded image file for format and size.

    Performs both magic bytes validation and file size validation.

    Args:
        data: The raw file bytes.

    Returns:
        A tuple of (is_valid, error_message, http_status_code).
        If valid, error_message is None and http_status_code is None.
        If invalid format, http_status_code is 400.
        If too large, http_status_code is 413.
    """
    # Check file size first
    size_valid, size_error = validate_file_size(data)
    if not size_valid:
        return False, size_error, 413

    # Check image format via magic bytes
    format_valid, format_error = validate_image_format(data)
    if not format_valid:
        return False, format_error, 400

    return True, None, None


def get_image_format(data: bytes) -> str | None:
    """Detect the image format from file content.

    Args:
        data: The raw file bytes.

    Returns:
        The detected format string ("png", "jpg", or "webp") or None
        if the format is not recognized.
    """
    return _check_magic_bytes(data)
