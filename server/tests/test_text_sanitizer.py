"""Unit tests for text sanitization utility."""

import pytest

from server.utils.text_sanitizer import (
    MAX_QUERY_LENGTH,
    normalize_whitespace,
    remove_special_characters,
    sanitize_text,
    truncate_text,
)


class TestSanitizeText:
    """Tests for the main sanitize_text function."""

    def test_empty_string(self):
        assert sanitize_text("") == ""

    def test_none_like_empty(self):
        assert sanitize_text("") == ""

    def test_plain_english_text(self):
        text = "Breaking news headline today"
        assert sanitize_text(text) == "Breaking news headline today"

    def test_plain_hebrew_text(self):
        text = "חדשות היום בישראל"
        assert sanitize_text(text) == "חדשות היום בישראל"

    def test_mixed_hebrew_english(self):
        text = "חדשות Breaking news היום"
        assert sanitize_text(text) == "חדשות Breaking news היום"

    def test_removes_special_characters(self):
        text = 'Hello "world" [test] (foo) {bar}'
        result = sanitize_text(text)
        assert '"' not in result
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
        assert ")" not in result
        assert "{" not in result
        assert "}" not in result

    def test_normalizes_whitespace(self):
        text = "  hello   world  \n  test  "
        result = sanitize_text(text)
        assert result == "hello world test"

    def test_truncates_long_text(self):
        text = "word " * 100  # 500 characters
        result = sanitize_text(text)
        assert len(result) <= MAX_QUERY_LENGTH

    def test_full_pipeline(self):
        text = '  "Breaking [news]"   in   Israel!  @today  '
        result = sanitize_text(text)
        # No dangerous chars
        for ch in '"[](){}!@#$%^&*+=;:?/\\|<>`~':
            assert ch not in result
        # No leading/trailing whitespace
        assert result == result.strip()
        # No double spaces
        assert "  " not in result


class TestRemoveSpecialCharacters:
    """Tests for remove_special_characters."""

    def test_removes_quotes(self):
        assert '"' not in remove_special_characters('say "hello"')
        assert "'" not in remove_special_characters("it's fine")

    def test_removes_brackets(self):
        result = remove_special_characters("[test] (value) {item}")
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
        assert ")" not in result
        assert "{" not in result
        assert "}" not in result

    def test_removes_operators(self):
        result = remove_special_characters("a & b | c ^ d ~ e")
        assert "&" not in result
        assert "|" not in result
        assert "^" not in result
        assert "~" not in result

    def test_removes_at_hash_percent(self):
        result = remove_special_characters("@user #tag 50%")
        assert "@" not in result
        assert "#" not in result
        assert "%" not in result

    def test_preserves_letters_and_digits(self):
        result = remove_special_characters("Hello123 World456")
        assert "Hello123" in result
        assert "World456" in result

    def test_preserves_hebrew(self):
        result = remove_special_characters("שלום עולם")
        assert "שלום" in result
        assert "עולם" in result

    def test_preserves_periods_commas_hyphens(self):
        result = remove_special_characters("hello, world. foo-bar")
        assert "," in result
        assert "." in result
        assert "-" in result


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace."""

    def test_collapses_multiple_spaces(self):
        assert normalize_whitespace("hello    world") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_handles_tabs_and_newlines(self):
        assert normalize_whitespace("hello\t\tworld\n\ntest") == "hello world test"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""

    def test_only_whitespace(self):
        assert normalize_whitespace("   \t\n  ") == ""


class TestTruncateText:
    """Tests for truncate_text."""

    def test_short_text_unchanged(self):
        text = "short text"
        assert truncate_text(text) == text

    def test_exact_length_unchanged(self):
        text = "a" * MAX_QUERY_LENGTH
        assert truncate_text(text) == text

    def test_long_text_truncated(self):
        text = "word " * 100
        result = truncate_text(text)
        assert len(result) <= MAX_QUERY_LENGTH

    def test_truncates_at_word_boundary(self):
        text = "hello world " * 50
        result = truncate_text(text, max_length=30)
        # Should not end mid-word
        assert not result.endswith(" ")
        assert len(result) <= 30

    def test_single_long_word_hard_cut(self):
        text = "a" * 300
        result = truncate_text(text, max_length=200)
        assert len(result) == 200

    def test_custom_max_length(self):
        text = "hello world this is a test"
        result = truncate_text(text, max_length=11)
        assert len(result) <= 11
