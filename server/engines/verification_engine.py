"""Verification Engine for searching the web and calculating confidence scores.

Searches extracted text against web sources using Google News RSS,
compares results using text similarity (Jaccard), and returns a confidence
score indicating whether the screenshot content is authentic.
"""

import time
import requests
from dataclasses import dataclass, field
from typing import Optional

from server.models.schemas import SearchResult
from server.utils.text_sanitizer import sanitize_text


# Confidence threshold: >= 0.5 means is_real=True
CONFIDENCE_THRESHOLD = 0.5

# Search timeout in seconds
SEARCH_TIMEOUT = 10

# Number of search results to request
NUM_SEARCH_RESULTS = 5


@dataclass
class VerificationResult:
    """Result of the verification process."""

    is_real: bool
    confidence: float
    sources: list[str] = field(default_factory=list)
    search_results: list[SearchResult] = field(default_factory=list)
    error: Optional[str] = None


class VerificationEngine:
    """Engine that searches the web for extracted text and determines authenticity.

    Uses googlesearch-python to find matching content, then calculates a
    confidence score based on text similarity (Jaccard) between the extracted
    text and search result titles/snippets.
    """

    def __init__(
        self,
        search_api_key: str = None,
        search_engine_id: str = None,
        num_results: int = NUM_SEARCH_RESULTS,
    ):
        """Initialize with optional Google Custom Search credentials.

        Args:
            search_api_key: Optional API key (reserved for future use).
            search_engine_id: Optional search engine ID (reserved for future use).
            num_results: Number of search results to fetch.
        """
        self.search_api_key = search_api_key
        self.search_engine_id = search_engine_id
        self.num_results = num_results

    def verify(self, extracted_text: str) -> VerificationResult:
        """Search for the text and calculate confidence score.

        Orchestrates the full verification pipeline:
        1. Sanitize the extracted text for search
        2. Search the web for matching content
        3. Calculate confidence based on text similarity

        Args:
            extracted_text: Text extracted from the screenshot via OCR.

        Returns:
            VerificationResult with confidence score and source URLs.
        """
        if not extracted_text or not extracted_text.strip():
            return VerificationResult(
                is_real=False,
                confidence=0.0,
                error="No text provided for verification",
            )

        # Sanitize text for search query
        query = sanitize_text(extracted_text)
        if not query:
            return VerificationResult(
                is_real=False,
                confidence=0.0,
                error="Text could not be sanitized into a valid query",
            )

        # Search the web
        search_results = self.search_web(query)

        # If search returned an error (empty results could be legitimate)
        if not search_results:
            return VerificationResult(
                is_real=False,
                confidence=0.0,
                sources=[],
                search_results=[],
                error=None,
            )

        # Calculate confidence from search results
        confidence = self.calculate_confidence(extracted_text, search_results)

        # Determine if real based on threshold
        is_real = confidence >= CONFIDENCE_THRESHOLD

        # Collect source URLs
        sources = [result.url for result in search_results]

        return VerificationResult(
            is_real=is_real,
            confidence=confidence,
            sources=sources,
            search_results=search_results,
        )

    def search_web(self, query: str) -> list[SearchResult]:
        """Search the web for the given query text.

        Uses Google News RSS feed which is reliable and doesn't get blocked.
        On failure, returns an empty list (caller handles gracefully).

        Args:
            query: Sanitized search query string.

        Returns:
            List of SearchResult objects from web search.
        """
        import urllib.parse
        import xml.etree.ElementTree as ET

        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(url, headers=headers, timeout=SEARCH_TIMEOUT)
            if response.status_code != 200:
                return []

            root = ET.fromstring(response.text)
            results = []

            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                description_el = item.find("description")

                if title_el is not None and link_el is not None:
                    # Google News titles often have " - Source" at the end
                    title = title_el.text or ""
                    # <source url="https://publisher.com">Publisher Name</source>
                    source_el = item.find("source")
                    actual_url = source_el.attrib.get("url", "") if source_el is not None else ""
                    source_name = source_el.text if source_el is not None else None
                    results.append(
                        SearchResult(
                            title=title,
                            url=actual_url if actual_url else (link_el.text or ""),
                            snippet=description_el.text or "" if description_el is not None else "",
                            source_name=source_name,
                        )
                    )
                    if len(results) >= self.num_results:
                        break

            return results

        except Exception:
            return []

    def calculate_confidence(
        self, extracted_text: str, search_results: list[SearchResult]
    ) -> float:
        """Compare extracted text against search results to determine confidence.

        Uses containment similarity — what fraction of the extracted text's
        words appear in search result titles. This is more forgiving than
        Jaccard when results have extra words (like source names).

        Args:
            extracted_text: Original text extracted from the screenshot.
            search_results: List of search results to compare against.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not search_results:
            return 0.0

        extracted_words = _tokenize(extracted_text)
        if not extracted_words:
            return 0.0

        max_similarity = 0.0

        for result in search_results:
            # Compare against title (most important) and snippet
            result_text = f"{result.title} {result.snippet}"
            result_words = _tokenize(result_text)

            if not result_words:
                continue

            # Containment: what fraction of extracted words are in the result?
            intersection = extracted_words & result_words
            containment = len(intersection) / len(extracted_words)
            max_similarity = max(max_similarity, containment)

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, max_similarity))


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase words.

    Splits on whitespace and removes empty tokens.

    Args:
        text: Input text to tokenize.

    Returns:
        Set of lowercase word tokens.
    """
    if not text:
        return set()
    return {word.lower() for word in text.split() if word.strip()}


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Calculate Jaccard similarity between two sets.

    Jaccard similarity = |A ∩ B| / |A ∪ B|

    Args:
        set_a: First set of tokens.
        set_b: Second set of tokens.

    Returns:
        Jaccard similarity coefficient between 0.0 and 1.0.
    """
    if not set_a and not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b

    if not union:
        return 0.0

    return len(intersection) / len(union)
