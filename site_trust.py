"""Site trust ratings based on NewsGuard and Media Bias/Fact Check data."""

from urllib.parse import urlparse

# (stars 1-3, Hebrew label)
_RATINGS: dict[str, tuple[int, str]] = {
    # ── High trust ──────────────────────────────────────────────────────────
    "reuters.com":          (3, "מהימן מאוד"),
    "apnews.com":           (3, "מהימן מאוד"),
    "bbc.com":              (3, "מהימן מאוד"),
    "bbc.co.uk":            (3, "מהימן מאוד"),
    "npr.org":              (3, "מהימן מאוד"),
    "pbs.org":              (3, "מהימן מאוד"),
    "theguardian.com":      (3, "מהימן מאוד"),
    "nytimes.com":          (3, "מהימן מאוד"),
    "washingtonpost.com":   (3, "מהימן מאוד"),
    "economist.com":        (3, "מהימן מאוד"),
    "ft.com":               (3, "מהימן מאוד"),
    "bloomberg.com":        (3, "מהימן מאוד"),
    "wsj.com":              (3, "מהימן מאוד"),
    "nbcnews.com":          (3, "מהימן מאוד"),
    "abcnews.go.com":       (3, "מהימן מאוד"),
    "cbsnews.com":          (3, "מהימן מאוד"),
    "usatoday.com":         (3, "מהימן מאוד"),
    "time.com":             (3, "מהימן מאוד"),
    "nature.com":           (3, "מהימן מאוד"),
    "scientificamerican.com": (3, "מהימן מאוד"),
    "haaretz.com":          (3, "מהימן מאוד"),
    "ynetnews.com":         (3, "מהימן מאוד"),
    # ── Medium trust ────────────────────────────────────────────────────────
    "cnn.com":              (2, "מהימן בדרך כלל"),
    "foxnews.com":          (2, "מהימן בדרך כלל"),
    "msnbc.com":            (2, "מהימן בדרך כלל"),
    "politico.com":         (2, "מהימן בדרך כלל"),
    "thehill.com":          (2, "מהימן בדרך כלל"),
    "newsweek.com":         (2, "מהימן בדרך כלל"),
    "forbes.com":           (2, "מהימן בדרך כלל"),
    "axios.com":            (2, "מהימן בדרך כלל"),
    "vox.com":              (2, "מהימן בדרך כלל"),
    "theatlantic.com":      (2, "מהימן בדרך כלל"),
    "wired.com":            (2, "מהימן בדרך כלל"),
    "techcrunch.com":       (2, "מהימן בדרך כלל"),
    "arstechnica.com":      (2, "מהימן בדרך כלל"),
    "theverge.com":         (2, "מהימן בדרך כלל"),
    "independent.co.uk":    (2, "מהימן בדרך כלל"),
    "telegraph.co.uk":      (2, "מהימן בדרך כלל"),
    "timesofisrael.com":    (2, "מהימן בדרך כלל"),
    "israelhayom.co.il":    (2, "מהימן בדרך כלל"),
    "maariv.co.il":         (2, "מהימן בדרך כלל"),
    "ynet.co.il":           (2, "מהימן בדרך כלל"),
    "huffpost.com":         (2, "מהימן בדרך כלל"),
    "slate.com":            (2, "מהימן בדרך כלל"),
    "vice.com":             (2, "מהימן בדרך כלל"),
    "nypost.com":           (2, "מהימן בדרך כלל"),
    "dailymail.co.uk":      (2, "מהימן בדרך כלל"),
    "newsmax.com":          (2, "מהימן בדרך כלל"),
    # ── Low trust / known misinformation ────────────────────────────────────
    "breitbart.com":        (1, "אמינות נמוכה"),
    "infowars.com":         (1, "אמינות נמוכה"),
    "naturalnews.com":      (1, "אמינות נמוכה"),
    "thegatewaypundit.com": (1, "אמינות נמוכה"),
    "zerohedge.com":        (1, "אמינות נמוכה"),
    "rt.com":               (1, "אמינות נמוכה"),
    "sputniknews.com":      (1, "אמינות נמוכה"),
    "oann.com":             (1, "אמינות נמוכה"),
}

_STARS = {3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}


def get_trust_rating(url: str) -> str | None:
    """Return a formatted trust-rating string for *url*, or None if unknown.

    Strips www. prefix and matches on the bare domain, e.g.:
        "https://www.reuters.com/world/…" → "⭐⭐⭐ מהימן מאוד (reuters.com)"
    """
    try:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return None

    entry = _RATINGS.get(domain)
    if entry is None:
        return None

    stars, label = entry
    return f"{_STARS[stars]} {label} ({domain})"
