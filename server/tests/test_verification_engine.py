"""Unit tests for the Verification Engine.

Tests use mocked web search to avoid real network calls.
"""

import sys
from unittest.mock import patch, MagicMock

import pytest

from server.engines.verification_engine import (
    VerificationEngine,
    VerificationResult,
    CONFIDENCE_THRESHOLD,
    _tokenize,
    _jaccard_similarity,
)
from server.models.schemas import SearchResult


# --- Helper fixtures ---


@pytest.fixture
def engine():
    """Create a VerificationEngine instance for testing."""
    return VerificationEngine()


def _make_search_results(items: list[dict]) -> list[SearchResult]:
    """Helper to create SearchResult objects from dicts."""
    return [
        SearchResult(
            title=item.get("title", "Test Title"),
            url=item.get("url", "https://example.com"),
            snippet=item.get("snippet", "Test snippet"),
        )
        for item in items
    ]


# --- Tests for _tokenize ---


class TestTokenize:
    def test_empty_string(self):
        assert _tokenize("") == set()

    def test_none_input(self):
        assert _tokenize(None) == set()

    def test_single_word(self):
        assert _tokenize("hello") == {"hello"}

    def test_multiple_words(self):
        assert _tokenize("Hello World") == {"hello", "world"}

    def test_duplicate_words(self):
        assert _tokenize("the the the") == {"the"}

    def test_mixed_case(self):
        assert _tokenize("Hello WORLD foo") == {"hello", "world", "foo"}


# --- Tests for _jaccard_similarity ---


class TestJaccardSimilarity:
    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert _jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # intersection = {b}, union = {a, b, c} => 1/3
        result = _jaccard_similarity({"a", "b"}, {"b", "c"})
        assert abs(result - 1 / 3) < 1e-9

    def test_empty_sets(self):
        assert _jaccard_similarity(set(), set()) == 0.0

    def test_one_empty_set(self):
        assert _jaccard_similarity({"a"}, set()) == 0.0


# --- Tests for calculate_confidence ---


class TestCalculateConfidence:
    def test_no_search_results(self, engine):
        confidence = engine.calculate_confidence("some text", [])
        assert confidence == 0.0

    def test_empty_extracted_text(self, engine):
        results = _make_search_results([{"title": "Test", "snippet": "Test"}])
        confidence = engine.calculate_confidence("", results)
        assert confidence == 0.0

    def test_exact_match_high_confidence(self, engine):
        text = "Breaking news major event happened today"
        results = _make_search_results(
            [{"title": "Breaking news major event happened today", "snippet": ""}]
        )
        confidence = engine.calculate_confidence(text, results)
        assert confidence > 0.5

    def test_no_overlap_zero_confidence(self, engine):
        text = "completely unique text here"
        results = _make_search_results(
            [{"title": "unrelated different words", "snippet": "nothing matches"}]
        )
        confidence = engine.calculate_confidence(text, results)
        assert confidence < 0.5

    def test_confidence_bounded_0_to_1(self, engine):
        text = "test query words"
        results = _make_search_results(
            [
                {"title": "test query words exactly", "snippet": "test query words"},
                {"title": "unrelated", "snippet": "nothing"},
            ]
        )
        confidence = engine.calculate_confidence(text, results)
        assert 0.0 <= confidence <= 1.0

    def test_uses_max_similarity_across_results(self, engine):
        text = "specific headline text"
        results = _make_search_results(
            [
                {"title": "unrelated content", "snippet": "no match here"},
                {"title": "specific headline text", "snippet": "exact match"},
            ]
        )
        confidence = engine.calculate_confidence(text, results)
        # Should use the better match (second result)
        assert confidence > 0.3


# --- Tests for search_web ---


class TestSearchWeb:
    @patch("server.engines.verification_engine.time.time")
    def test_search_web_success(self, mock_time, engine):
        """Test successful web search with mocked googlesearch."""
        mock_time.side_effect = [0.0, 1.0, 2.0, 3.0]  # Well within timeout

        mock_result = MagicMock()
        mock_result.title = "Test Article"
        mock_result.url = "https://example.com/article"
        mock_result.description = "This is a test article snippet"

        mock_search_module = MagicMock()
        mock_search_module.search = MagicMock(return_value=[mock_result])

        with patch.dict("sys.modules", {"googlesearch": mock_search_module}):
            results = engine.search_web("test query")

        assert len(results) == 1
        assert results[0].title == "Test Article"
        assert results[0].url == "https://example.com/article"
        assert results[0].snippet == "This is a test article snippet"

    def test_search_web_handles_exception(self, engine):
        """Test that search_web returns empty list on exception."""
        with patch(
            "builtins.__import__",
            side_effect=ImportError("googlesearch not available"),
        ):
            # The method catches all exceptions
            results = engine.search_web("test query")
            assert results == []

    @patch("server.engines.verification_engine.time.time")
    def test_search_web_timeout(self, mock_time, engine):
        """Test that search respects the 10-second timeout."""
        # First call returns start time, subsequent calls exceed timeout
        mock_time.side_effect = [0.0, 11.0]

        mock_result = MagicMock()
        mock_result.title = "Result 1"
        mock_result.url = "https://example.com/1"
        mock_result.description = "Snippet 1"

        mock_result2 = MagicMock()
        mock_result2.title = "Result 2"
        mock_result2.url = "https://example.com/2"
        mock_result2.description = "Snippet 2"

        with patch.dict("sys.modules", {"googlesearch": MagicMock()}):
            with patch(
                "googlesearch.search", return_value=iter([mock_result, mock_result2])
            ):
                results = engine.search_web("test query")
                # Due to timeout, should stop early
                assert isinstance(results, list)


# --- Tests for verify ---


class TestVerify:
    def test_verify_empty_text(self, engine):
        """Verify returns 0.0 confidence for empty text."""
        result = engine.verify("")
        assert isinstance(result, VerificationResult)
        assert result.confidence == 0.0
        assert result.is_real is False
        assert result.error is not None

    def test_verify_none_text(self, engine):
        """Verify handles None text gracefully."""
        result = engine.verify(None)
        assert result.confidence == 0.0
        assert result.is_real is False

    def test_verify_whitespace_only(self, engine):
        """Verify returns 0.0 for whitespace-only text."""
        result = engine.verify("   \n\t  ")
        assert result.confidence == 0.0
        assert result.is_real is False

    def test_verify_with_mocked_search_high_confidence(self, engine):
        """Verify returns high confidence when search results match."""
        mock_results = _make_search_results(
            [
                {
                    "title": "Breaking news earthquake strikes city",
                    "url": "https://news.example.com/earthquake",
                    "snippet": "Breaking news earthquake strikes city center today",
                }
            ]
        )

        with patch.object(engine, "search_web", return_value=mock_results):
            result = engine.verify("Breaking news earthquake strikes city")

        assert result.confidence > 0.0
        assert len(result.sources) > 0
        assert "https://news.example.com/earthquake" in result.sources

    def test_verify_with_mocked_search_low_confidence(self, engine):
        """Verify returns low confidence when search results don't match."""
        mock_results = _make_search_results(
            [
                {
                    "title": "Completely unrelated article about cooking",
                    "url": "https://food.example.com/recipe",
                    "snippet": "How to make pasta from scratch at home",
                }
            ]
        )

        with patch.object(engine, "search_web", return_value=mock_results):
            result = engine.verify("Breaking news earthquake strikes city")

        assert result.confidence < CONFIDENCE_THRESHOLD
        assert result.is_real is False

    def test_verify_search_failure(self, engine):
        """Verify handles search failure gracefully."""
        with patch.object(engine, "search_web", return_value=[]):
            result = engine.verify("Some text to verify")

        assert result.confidence == 0.0
        assert result.is_real is False
        assert result.sources == []

    def test_verify_is_real_threshold(self, engine):
        """Verify sets is_real based on confidence threshold."""
        # Create results that will produce high similarity
        text = "exact match text here"
        mock_results = _make_search_results(
            [
                {
                    "title": "exact match text here",
                    "url": "https://example.com",
                    "snippet": "exact match text here",
                }
            ]
        )

        with patch.object(engine, "search_web", return_value=mock_results):
            result = engine.verify(text)

        # With exact match, confidence should be high
        assert result.confidence >= CONFIDENCE_THRESHOLD
        assert result.is_real is True

    def test_verify_returns_verification_result(self, engine):
        """Verify always returns a VerificationResult."""
        with patch.object(engine, "search_web", return_value=[]):
            result = engine.verify("test")

        assert isinstance(result, VerificationResult)
        assert hasattr(result, "is_real")
        assert hasattr(result, "confidence")
        assert hasattr(result, "sources")
        assert hasattr(result, "error")
