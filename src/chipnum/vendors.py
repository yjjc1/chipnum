"""Vendor and category resolution from a normalised part number.

The vendor table lives in ``data/vendors.toml`` so that adding a vendor is a
data edit, never a code change. This module loads it, resolves prefixes
longest-first (so ``STM32`` wins over ``ST``), and caches the result.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path

from .categories import category_label
from .normalize import compact, fold, normalise

_DATA = Path(__file__).parent / "data"

# Every ``*.toml`` in the data directory is concatenated into one table, in
# filename order. That keeps the hand-curated core table readable while
# letting focused follow-up batches live in their own files.
_TABLES = ("vendors.toml", "vendors_mining.toml")


@dataclass(frozen=True)
class Match:
    """Result of resolving a part number."""

    pn: str
    vendor: str | None = None
    category: str = "unknown"
    confidence: str = "none"
    vendor_aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def category_label(self) -> str:
        return category_label(self.category)

    @property
    def matched(self) -> bool:
        return self.vendor is not None

    def as_dict(self) -> dict:
        return {
            "pn": self.pn,
            "vendor": self.vendor,
            "category": self.category,
            "category_label": self.category_label,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class _Prefix:
    prefix: str
    category: str
    vendor: str
    priority: int


def _parse_vendor_table(path: Path) -> list[_Prefix]:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
        import tomli as tomllib  # type: ignore[no-redef]

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    out: list[_Prefix] = []
    for idx, vendor in enumerate(data.get("vendor", [])):
        name = vendor["name"]
        for p in vendor.get("prefixes", []):
            prefix = p["p"]
            # Longer, more specific prefixes are checked first. The tiebreak
            # on vendor order keeps resolution deterministic when two vendors
            # declare the same prefix.
            out.append(
                _Prefix(
                    prefix=prefix,
                    category=p.get("cat", "unknown"),
                    vendor=name,
                    priority=len(prefix) * 100 - idx,
                )
            )
    out.sort(key=lambda x: x.priority, reverse=True)
    return out


@functools.lru_cache(maxsize=1)
def _table() -> tuple[_Prefix, ...]:
    entries: list[_Prefix] = []
    for name in _TABLES:
        path = _DATA / name
        if path.exists():
            entries.extend(_parse_vendor_table(path))
    entries.sort(key=lambda x: x.priority, reverse=True)
    return tuple(entries)


@functools.lru_cache(maxsize=1)
def _raw_vendor_blocks() -> list[dict]:
    """All ``[[vendor]]`` blocks across every table file, in order."""
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

    blocks: list[dict] = []
    for name in _TABLES:
        path = _DATA / name
        if not path.exists():
            continue
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        blocks.extend(data.get("vendor", []))
    return blocks


@functools.lru_cache(maxsize=1)
def vendor_names() -> tuple[str, ...]:
    seen: list[str] = []
    for p in _table():
        if p.vendor not in seen:
            seen.append(p.vendor)
    return tuple(seen)


@functools.lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    """Map user-facing vendor aliases (``TI``, ``德州仪器``) to canonical names."""
    alias_map: dict[str, str] = {}
    for vendor in _raw_vendor_blocks():
        canonical = vendor["name"]
        for alias in vendor.get("aliases", []):
            key = alias.strip().lower()
            if key:
                alias_map.setdefault(key, canonical)
        alias_map.setdefault(canonical.lower(), canonical)
    return alias_map


def resolve_vendor(name: str) -> str | None:
    """Resolve a user-typed vendor name/alias to its canonical form."""
    return _aliases().get(str(name).strip().lower())


# One- or two-letter package/lead codes that vendors prepend to a series
# name. "U74LVC1G125G" is an NXP 74LVC part in a TSSOP package, not a part
# from a vendor called "U".
_PACKAGE_CODES = frozenset({"U", "T", "R", "D", "P", "B", "C", "S", "M", "N"})


def lookup(pn: str) -> Match:
    """Resolve ``pn`` to a vendor and category.

    Matching is tried on the normalised form first (``STM32-F103`` matches
    ``STM32``), then on the separator-free form so that a part number which
    hyphenates differently from the vendor's datasheet still resolves.

    >>> lookup("stm32f103c8t6").vendor
    'STMicroelectronics'
    >>> lookup("LMX9838SB").vendor
    'Texas Instruments'
    >>> lookup("nRF52840-QIAA").vendor
    'Nordic Semiconductor'
    >>> lookup("U74LVC1G125G").vendor
    'NXP Semiconductors'

    Matching runs longest-prefix-first across three candidate forms: the
    normalised string, its separator-free version, and the original text
    upper/lower-cased. The third form matters because a few vendors embed
    meaningful lowercase (``nRF``, ``iNAND``) that ``normalise`` destroys.
    """
    norm = normalise(pn)
    if not norm:
        return Match(pn="")

    original = fold(str(pn or ""))
    candidates = [norm, compact(norm)]
    # Preserve case-significant variants: nRF52840 upper-cases to NRF52840,
    # which is not the prefix the table records. The original text and its
    # upper-cased form are both tried so "nRF52840" and "NRF52840" resolve
    # identically.
    if original and original not in candidates:
        candidates.append(original)
    if original:
        upper_original = original.upper()
        if upper_original not in candidates:
            candidates.append(upper_original)
    # A lower-cased table prefix ("nRF") must still match an upper-cased
    # candidate. Compare case-insensitively as a final pass.
    lower_candidates = [c.lower() for c in candidates if c]

    # Two passes. The first only considers prefixes of three characters or
    # more; the second falls back to two-character prefixes.
    #
    # This ordering is what keeps "IPD50N06S2L" (an Infineon OptiMOS) from
    # being claimed by a two-letter prefix, and "MLX90614" (Melexis) from
    # being called ROHM. A two-character prefix is weak evidence on its own
    # and must never outrank a specific one, but it is still worth reporting
    # as a low-confidence match rather than dropping the part entirely.
    for min_len, confidence in ((3, "high"), (2, "low")):
        for candidate in candidates:
            if not candidate:
                continue
            match = _first_match(candidate, min_len)
            if match is not None:
                pref, vendor, category = match
                return Match(
                    pn=norm,
                    vendor=vendor,
                    category=category,
                    confidence=confidence,
                )
            # Retry with a leading package code stripped. Only done when the
            # bare lookup failed, so a genuine vendor that happens to start
            # with one of these letters ("TI" parts) is never displaced.
            if len(candidate) > 4 and candidate[0] in _PACKAGE_CODES:
                match = _first_match(candidate[1:], min_len)
                if match is not None:
                    pref, vendor, category = match
                    return Match(
                        pn=norm,
                        vendor=vendor,
                        category=category,
                        confidence=confidence,
                    )

    for lower_candidate in lower_candidates:
        for pref in _table():
            if lower_candidate.startswith(pref.prefix.lower()):
                return Match(
                    pn=norm,
                    vendor=pref.vendor,
                    category=pref.category,
                    confidence="low" if len(pref.prefix) <= 2 else "high",
                )
    return Match(pn=norm)


def _first_match(candidate: str, min_len: int) -> tuple[_Prefix, str, str] | None:
    """Return the longest prefix of at least ``min_len`` that matches."""
    best: _Prefix | None = None
    for pref in _table():
        if len(pref.prefix) < min_len:
            continue
        if not candidate.startswith(pref.prefix):
            continue
        if best is None or len(pref.prefix) > len(best.prefix):
            best = pref
    if best is None:
        return None
    return best, best.vendor, best.category


@dataclass(frozen=True)
class Identity:
    """A part number's stable identity, independent of how it was spelled.

    Two part numbers that denote the same die share a ``key``, even when they
    are written differently (``STM32F103C8T6`` vs ``STM32-F103C8T6``). This
    is what you join on when merging two BOMs, or a BOM with a set of
    articles, and it is deliberately separate from :class:`Match` — a match
    describes one spelling, an identity describes the die.
    """

    pn: str
    key: str
    vendor: str | None = None
    category: str = "unknown"
    confidence: str = "none"

    def as_dict(self) -> dict:
        return {
            "pn": self.pn,
            "key": self.key,
            "vendor": self.vendor,
            "category": self.category,
            "confidence": self.confidence,
        }


def identity(pn: str) -> Identity:
    """Return the stable identity of ``pn``.

    >>> identity("stm32 f103c8t6").key
    'STM32F103C8T6'
    >>> identity("STM32-F103C8T6").key == identity("stm32f103c8t6").key
    True
    """
    norm = normalise(pn)
    key = compact(norm)
    match = lookup(norm)
    return Identity(
        pn=norm,
        key=key,
        vendor=match.vendor,
        category=match.category,
        confidence=match.confidence,
    )


def lookup_many(pns: list[str]) -> dict[str, Match]:
    """Resolve a batch, deduplicating repeated part numbers."""
    out: dict[str, Match] = {}
    for pn in pns:
        norm = normalise(pn)
        if norm and norm not in out:
            out[norm] = lookup(norm)
    return out