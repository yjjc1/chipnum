"""Audit the vendor prefix table for collisions and low-confidence prefixes.

Run as part of the test suite: a prefix table that silently misattributes a
part number is worse than one that admits ignorance, because downstream
buying decisions inherit the error.

Three classes of defect are reported:

``collision``
    Vendor A's prefix is a strict prefix of vendor B's prefix (A="TM",
    B="TMP"), and A sorts first. Whichever order the table happens to be in
    decides the answer, which is not a property anyone can reason about.

``overshadow``
    A short prefix wins over a longer, more specific one on real corpus data.

``low_confidence``
    A prefix is so short and generic ("A2", "M1", "TM") that it will collide
    with unrelated vocabularies. These are reported for human review, not
    automatically removed.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from .vendors import _table

# Prefixes shorter than this are flagged for review: below this length the
# prefix stops being evidence of anything.
GENERIC_LEN = 3

# Prefixes that are known-safe regardless of length because they are
# distinctive enough on their own (verified by hand against the corpus).
_ALLOW_GENERIC = frozenset({"BCP", "SEP", "HOP", "RCH"})


def find_collisions() -> list[tuple[str, str, str]]:
    """Return ``(short_vendor, short_prefix, longer_prefix)`` triples.

    ``short_vendor`` wins whenever the part number starts with
    ``longer_prefix``, because it sorts first. Any such pair is a latent bug.
    """
    entries = [(p.vendor, p.prefix) for p in _table()]
    by_vendor: dict[str, set[str]] = defaultdict(set)
    for vendor, prefix in entries:
        by_vendor[vendor].add(prefix)

    out: list[tuple[str, str, str]] = []
    for vendor_a, prefixes_a in by_vendor.items():
        for vendor_b, prefixes_b in by_vendor.items():
            if vendor_a == vendor_b:
                continue
            for pa in prefixes_a:
                for pb in prefixes_b:
                    # pb strictly extends pa, and pa sorts before pb.
                    if pb.startswith(pa) and len(pb) > len(pa):
                        out.append((vendor_a, pa, pb))
    return out


def find_generic_prefixes() -> list[tuple[str, str]]:
    """Return prefixes short enough to be ambiguous with ordinary English."""
    out = []
    for pref in _table():
        if len(pref.prefix) <= GENERIC_LEN and pref.prefix not in _ALLOW_GENERIC:
            out.append((pref.vendor, pref.prefix))
    return sorted(set(out), key=lambda x: (len(x[1]), x[1]))


def find_shadowed(corpus: list[str]) -> list[tuple[str, str, str]]:
    """Report part numbers where a short prefix beat a longer specific one.

    ``corpus`` is a list of real part numbers. For each one, collect every
    vendor whose prefix matches; if more than one matches, the winner is the
    longest prefix — but the table's sort order decides it, so record any case
    where the chosen vendor is not the longest-prefix match.
    """
    from .normalize import normalise
    from .vendors import lookup

    out: list[tuple[str, str, str]] = []
    table = _table()
    for raw in corpus:
        pn = normalise(raw)
        if not pn:
            continue
        matching = [p for p in table if pn.startswith(p.prefix)]
        if len(matching) < 2:
            continue
        best = max(matching, key=lambda p: len(p.prefix))
        chosen = lookup(pn).vendor
        if chosen != best.vendor:
            out.append((pn, str(chosen), best.vendor))
    return out


def report(corpus: list[str] | None = None) -> str:
    """Render a human-readable audit report."""
    lines: list[str] = []
    collisions = find_collisions()
    lines.append(f"prefix collisions: {len(collisions)}")
    for vendor, short, long in collisions[:40]:
        lines.append(f"  {vendor}: '{short}' shadows ...'{long}'")

    generic = find_generic_prefixes()
    lines.append(f"\ngeneric prefixes (len <= {GENERIC_LEN}): {len(generic)}")
    for vendor, prefix in generic[:60]:
        lines.append(f"  {vendor}: '{prefix}'")

    if corpus:
        shadowed = find_shadowed(corpus)
        lines.append(f"\nshadowed on corpus: {len(shadowed)}")
        for pn, chosen, best in shadowed[:40]:
            lines.append(f"  {pn}: chose {chosen}, longest prefix is {best}")

    return "\n".join(lines)

def _main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m chipnum.audit``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m chipnum.audit",
        description="Check the vendor prefix table for collisions and weak prefixes.",
    )
    parser.add_argument(
        "--corpus",
        help="file with one part number per line; enables shadow detection",
    )
    parser.add_argument(
        "--max-collisions",
        type=int,
        default=60,
        help="exit non-zero above this many collisions (default: 60)",
    )
    args = parser.parse_args(argv)

    corpus: list[str] = []
    if args.corpus:
        from pathlib import Path

        text = Path(args.corpus).read_text(encoding="utf-8", errors="replace")
        from .normalize import normalise

        corpus = [normalise(t) for t in text.split()]

    print(report(corpus))

    collisions = find_collisions()
    if len(collisions) > args.max_collisions:
        print(
            f"\nFAIL: {len(collisions)} collisions exceeds the limit of "
            f"{args.max_collisions}. Review the vendor tables.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main())
