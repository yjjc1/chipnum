"""chipnum — extract, normalise and classify semiconductor part numbers."""

from __future__ import annotations

from .categories import CATEGORIES, category_label
from .extract import Candidate, extract, extract_unique, score_token
from .normalize import compact, is_plausible, normalise, split_suffix
from .vendors import Match, lookup, lookup_many, resolve_vendor, vendor_names

__version__ = "0.1.0"

__all__ = [
    "CATEGORIES",
    "Candidate",
    "Match",
    "category_label",
    "compact",
    "extract",
    "extract_unique",
    "is_plausible",
    "lookup",
    "lookup_many",
    "normalise",
    "resolve_vendor",
    "score_token",
    "split_suffix",
    "vendor_names",
    "__version__",
]