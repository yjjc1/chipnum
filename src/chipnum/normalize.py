"""Normalisation of raw part-number strings.

Every downstream stage works on the *normalised* form, so this module is the
single place where "what does a part number look like" is decided.

Normalisation rules
-------------------
1. Unicode is folded to NFKC, which turns full-width ``ＳＴＭ３２`` into
   ``STM32`` and the CJK full-width hyphen ``－`` into ``-``.
2. Whitespace and invisible characters (zero-width space, BOM) are removed.
3. Upper-cased: real part numbers are case-insensitive in the wild
   (``stm32f103`` and ``STM32F103`` are the same die).
4. Trailing and leading separators (``,`` ``.`` ``;`` ``/`` ``_`` ``-``) are
   stripped, because OCR and copy-paste reliably pick them up at the edges.
5. Internal separators are canonicalised to ``-``.

Canonical form used as the dictionary key is ``normalise(pn)`` — the string
with separators kept. ``compact(pn)`` drops separators entirely and is used
for fuzzy matching when vendors disagree about hyphenation.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that routinely surround a part number in prose and tables.
_EDGE_JUNK = re.compile(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$")

# Zero-width and bidi characters that survive copy-paste and OCR. Note that
# ordinary whitespace is NOT in here: a space between two runs is a separator,
# and must go through _SEPARATORS so "STM32 F103" canonicalises to
# "STM32-F103" like "STM32_F103" does. Deleting it instead silently produces
# a different canonical form depending on which separator the author typed.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]+")

# Separators that are equivalent in the wild.
_SEPARATORS = re.compile(r"[\s_/,;:·]+")

# Trailing punctuation that survives _EDGE_JUNK when glued to a suffix letter.
_TRAILING_PUNCT = re.compile(r"[.,;:'\"`]+$")


def fold(text: str) -> str:
    """NFKC-fold and strip invisibles, without touching case or separators."""
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE.sub("", text)
    return text


def normalise(raw: str) -> str:
    """Return the canonical form of ``raw``.

    >>> normalise(" stm32f103c8t6 ")
    'STM32F103C8T6'
    >>> normalise("ＳＴＭ３２－Ｆ１０３")
    'STM32-F103'
    >>> normalise("LMX9838SB,")
    'LMX9838SB'
    """
    if raw is None:
        return ""
    text = fold(str(raw)).upper()
    text = _SEPARATORS.sub("-", text)
    text = _TRAILING_PUNCT.sub("", text)
    text = _EDGE_JUNK.sub("", text)
    return text


def compact(raw: str) -> str:
    """Return the separator-free form, for fuzzy comparison.

    ``LMX-9838SB`` and ``LMX9838SB`` collapse to the same key.
    """
    return normalise(raw).replace("-", "")


def split_suffix(raw: str) -> tuple[str, str]:
    """Split ``raw`` into (base, suffix) at the last hyphen.

    ``IRFP9140NPBF`` -> ``('IRFP9140NPBF', '')``
    ``TMUX1308PWR``  -> ``('TMUX1308PWR', '')``
    ``JLX-3B``       -> ``('JLX', '3B')``

    The suffix is where package, temperature grade and packing information
    usually lives, so downstream code treats it separately.
    """
    norm = normalise(raw)
    if "-" not in norm:
        return norm, ""
    base, _, suffix = norm.rpartition("-")
    return base, suffix


def is_plausible(raw: str, *, min_len: int = 4, max_len: int = 24) -> bool:
    """Cheap structural gate before the expensive vendor lookup.

    Rejects strings that cannot be part numbers at all: pure digits, pure
    punctuation, and anything outside the length window. This is a *floor*,
    not a decision — see :mod:`chipnum.extract` for scoring.
    """
    norm = normalise(raw)
    if not (min_len <= len(norm) <= max_len):
        return False
    return bool(re.search(r"\d", norm)) and bool(re.search(r"[A-Za-z]", norm))