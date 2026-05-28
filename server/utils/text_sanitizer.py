"""Text sanitization utility for cleaning OCR-extracted text before web search queries.

Removes or escapes special characters that could cause search API issues,
normalizes whitespace, and truncates to a reasonable query length.
Handles both Hebrew and English text.
"""

import re

# Maximum length for a search query (characters)
MAX_QUERY_LENGTH = 200

# Characters that could cause issues with search APIs (operators, brackets, quotes, etc.)
DANGEROUS_CHARS_PATTERN = re.compile(
    r'["\'\[\]\(\)\{\}<>|\\&^~`!@#$%*+=;:?/]'
)


def sanitize_text(text: str) -> str:
    """Sanitize extracted text for use as a search query.

    Steps:
    1. Remove special characters that could break search queries
    2. Normalize whitespace (collapse multiple spaces, strip edges)
    3. Truncate to MAX_QUERY_LENGTH characters (break at word boundary)

    Args:
        text: Raw text extracted from OCR.

    Returns:
        Sanitized text safe for use in search queries.
    """
    if not text:
        return ""

    # Remove special/dangerous characters
    cleaned = remove_special_characters(text)

    # Normalize whitespace
    cleaned = normalize_whitespace(cleaned)

    # Truncate to max length
    cleaned = truncate_text(cleaned, MAX_QUERY_LENGTH)

    return cleaned


def remove_special_characters(text: str) -> str:
    """Remove special characters that could cause search API issues.

    Preserves Hebrew characters, English letters, digits, basic punctuation
    (periods, commas, hyphens, spaces), and common Unicode letters.

    Args:
        text: Input text potentially containing dangerous characters.

    Returns:
        Text with dangerous characters removed.
    """
    # Remove characters that are problematic for search APIs
    cleaned = DANGEROUS_CHARS_PATTERN.sub(" ", text)
    return cleaned


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Collapses multiple consecutive whitespace characters (spaces, tabs,
    newlines) into a single space and strips leading/trailing whitespace.

    Args:
        text: Input text with potentially irregular whitespace.

    Returns:
        Text with normalized whitespace.
    """
    # Replace any whitespace sequence (including newlines, tabs) with single space
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def truncate_text(text: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    """Truncate text to a maximum length, breaking at a word boundary.

    If the text exceeds max_length, it is cut at the last space before
    the limit to avoid splitting words.

    Args:
        text: Input text to truncate.
        max_length: Maximum allowed length (default: MAX_QUERY_LENGTH).

    Returns:
        Truncated text, at most max_length characters.
    """
    if len(text) <= max_length:
        return text

    # Cut at max_length and find last space to avoid splitting a word
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > 0:
        return truncated[:last_space].rstrip()

    # No space found — just hard-cut (single very long word)
    return truncated
