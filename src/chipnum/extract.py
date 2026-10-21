"""Extraction of part numbers from free text.

The extractor is intentionally conservative: a false positive (``GB300``,
``RC0805`` reading as "some resistor") costs a maintainer more trust than a
missed part number costs coverage, because the tool's whole job is to be
believed. Every candidate therefore carries a score and a set of reasons, and
:func:`extract` exposes the threshold so callers can trade precision for recall.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import compact, is_plausible, normalise
from .vendors import lookup

# Candidate tokens: runs of alphanumerics joined by - / _ . , bounded by
# non-part characters. Deliberately excludes bare years and pure numbers.
_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9][A-Za-z0-9._/-]{3,31}[A-Za-z0-9](?![A-Za-z0-9])")

# Tokens that are never part numbers even though they match the shape.
_STOPWORDS = frozenset(
    """
    APPLE ANDROID WINDOWS GOOGLE AMAZON MICROSOFT NVIDIA INTEL AMD
    PRICE PRICES STOCK STOCKS SHARES MARKET MARKETS SUPPLY SUPPLIES
    Q Q1 Q2 Q3 Q4 YYYY JAN FEB MAR APR JUN JUL AUG SEP OCT NOV DEC
    USD CNY RMB EUR JPY
    """.split()
)

# Generic words that appear in industry prose and would otherwise score as
# short part numbers.
_PROSE = frozenset(
    """
    MOS FETS GATE DRIVER SERIAL PARALLEL SPI I2C USB TYPE PCIE DDR
    WIDE INPUT OUTPUT HIGH LOW BUCK BOOST LINEAR SWITCHING
    REAL TIME RANDOM ACCESS NON VOLATILE STATIC RAM
    """.split()
)

# Patterns that indicate a part number even without a vendor prefix match,
# e.g. a package code or a trailing grade letter.
_STRONG_HINT = re.compile(r"(?:\d[A-Z]|[A-Z]\d)[A-Z]*[-_]?\d")


@dataclass
class Candidate:
    """One extracted token plus why it scored the way it did."""

    raw: str
    pn: str
    score: float
    reasons: list[str] = field(default_factory=list)
    vendor: str | None = None
    category: str = "unknown"

    @property
    def matched(self) -> bool:
        return self.vendor is not None

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "pn": self.pn,
            "score": round(self.score, 3),
            "vendor": self.vendor,
            "category": self.category,
            "reasons": self.reasons,
        }


def score_token(raw: str) -> Candidate:
    """Score a single token as a part number.

    The score is a sum of independent signals rather than a rule cascade, so
    that ``reasons`` can explain *why* something was accepted — which is what
    makes threshold tuning possible instead of guesswork.
    """
    pn = normalise(raw)
    cand = Candidate(raw=raw, pn=pn, score=0.0)
    if not pn:
        return cand

    core = pn.replace("-", "")

    # --- negative signals -------------------------------------------------
    if pn in _STOPWORDS or core in _STOPWORDS:
        cand.score -= 10.0
        cand.reasons.append("stopword")
    if core in _PROSE:
        cand.score -= 4.0
        cand.reasons.append("prose-word")
    if not is_plausible(pn):
        cand.score -= 5.0
        cand.reasons.append("implausible-shape")

    # --- positive signals -------------------------------------------------
    match = lookup(pn)
    cand.vendor = match.vendor
    cand.category = match.category

    if match.vendor:
        # A vendor prefix match is the single strongest signal available.
        cand.score += 5.0
        cand.reasons.append(f"vendor:{match.vendor}")
        if match.confidence == "low":
            # The match rests on a two-character prefix, which is weak
            # evidence. It is reported, but it must not be presented with the
            # same authority as a specific one.
            cand.score -= 2.0
            cand.reasons.append("weak-prefix")

    if _STRONG_HINT.search(pn):
        cand.score += 1.5
        cand.reasons.append("alnum-mix")

    # Real part numbers sit in the 6-18 character band.
    if 6 <= len(core) <= 18:
        cand.score += 1.5
        cand.reasons.append("length-band")
    elif len(core) <= 4:
        cand.score -= 2.0
        cand.reasons.append("too-short")

    # Hyphenated part numbers are usually real; bare 5-letter words are not.
    if "-" in pn:
        cand.score += 1.0
        cand.reasons.append("hyphenated")

    # A vendor prefix that is itself the whole string (e.g. "ST", "TI") is a
    # company mention, not a part number.
    if match.vendor and core == normalise(match.vendor).replace(" ", "")[: len(core)]:
        if len(core) <= 3:
            cand.score -= 6.0
            cand.reasons.append("vendor-mention")

    return cand


def extract(
    text: str,
    *,
    threshold: float = 5.0,
    include_unmatched: bool = False,
) -> list[Candidate]:
    """Extract part-number candidates from ``text``.

    Args:
        text: any chunk of prose, markdown, CSV cell or plain text.
        threshold: minimum score to keep. Raise it for precision, lower it
            for recall. ``5.0`` keeps vendor-confirmed parts plus the very
            best-shaped unknowns.
        include_unmatched: also return candidates that matched no vendor.
            Useful for auditing what the table is missing.

    Returns:
        Candidates sorted by descending score.
    """
    results: list[Candidate] = []
    seen: set[str] = set()

    for match in _CANDIDATE.finditer(text or ""):
        raw = match.group(0)
        pn = normalise(raw)
        if not pn or pn in seen:
            continue
        seen.add(pn)

        cand = score_token(raw)
        if cand.score < threshold:
            continue
        if not include_unmatched and not cand.matched:
            continue
        results.append(cand)

    results.sort(key=lambda c: (-c.score, c.pn))
    return results


def extract_unique(text: str, *, threshold: float = 5.0) -> list[Candidate]:
    """Like :func:`extract` but deduplicated by canonical part number.

    Deduplication is by *separator-free* key, because ``STM32-G491RET6`` and
    ``STM32G491RET6`` are the same die and must not be counted twice. The
    highest-scoring spelling is kept, since that is the one that matched a
    vendor.
    """
    out: list[Candidate] = []
    seen: dict[str, Candidate] = {}
    for cand in extract(text, threshold=threshold):
        key = compact(cand.pn)
        if key in seen:
            if cand.score > seen[key].score:
                seen[key] = cand
            continue
        seen[key] = cand
        out.append(cand)
    out.sort(key=lambda c: (-c.score, c.pn))
    return out