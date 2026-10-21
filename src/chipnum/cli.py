"""Command-line interface for chipnum.

Three subcommands, chosen so that the common cases need no code at all:

``chipnum extract``   pull part numbers out of text, files or stdin
``chipnum lookup``    resolve specific part numbers (batch, for a BOM)
``chipnum vendors``   list the vendor/category table, or audit it
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .audit import report
from .extract import extract_unique
from .normalize import normalise
from .vendors import lookup_many, vendor_names


def _read_inputs(paths: list[str] | str) -> tuple[str, int]:
    """Read every path as text. ``-`` means stdin.

    Accepts a single path as well as a list, so callers cannot accidentally
    iterate a filename character by character.

    Returns ``(text, failures)`` so callers can exit non-zero instead of
    silently producing an empty result — a BOM file that failed to open and
    an empty BOM file must not look the same.
    """
    if isinstance(paths, str):
        paths = [paths]
    chunks: list[str] = []
    failures = 0
    for p in paths:
        if p == "-":
            chunks.append(sys.stdin.read())
            continue
        try:
            chunks.append(Path(p).read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            print(f"chipnum: cannot read {p}: {exc}", file=sys.stderr)
            failures += 1
    return "\n".join(chunks), failures


def _die_on_failure(failures: int) -> None:
    if failures:
        # Raised as an exception so it propagates out of the command
        # functions; main() catches it and returns the code. Raising SystemExit
        # directly from here would escape main() as an exception, which is
        # wrong for a function documented to return an exit code.
        raise _InputError(failures)


class _InputError(Exception):
    """Raised when an input file could not be read."""

    def __init__(self, failures: int):
        super().__init__(f"{failures} input file(s) could not be read")
        self.failures = failures


def _write_rows(rows: list[dict], fmt: str, stream) -> None:
    if fmt == "json":
        json.dump(rows, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        return
    if not rows:
        return
    writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def cmd_extract(args: argparse.Namespace) -> int:
    text, failures = _read_inputs(args.inputs)
    _die_on_failure(failures)
    cands = extract_unique(text, threshold=args.threshold)

    if args.unmatched:
        from .extract import extract

        seen = {c.pn for c in cands}
        for c in extract(text, threshold=args.threshold, include_unmatched=True):
            if c.pn not in seen:
                cands.append(c)

    rows = [c.as_dict() for c in cands]
    _write_rows(rows, args.format, sys.stdout)

    if args.summary:
        vendors = Counter(c.vendor for c in cands if c.vendor)
        cats = Counter(c.category for c in cands if c.matched)
        matched = sum(1 for c in cands if c.matched)
        if cands:
            print(
                f"\n{len(cands)} unique candidates, {matched} vendor-matched "
                f"({matched / len(cands) * 100:.1f}%)",
                file=sys.stderr,
            )
        else:
            print("\nno candidates", file=sys.stderr)
        if vendors:
            print("\ntop vendors:", file=sys.stderr)
            for v, n in vendors.most_common(args.top):
                print(f"  {n:>5}  {v}", file=sys.stderr)
        if cats:
            print("\ntop categories:", file=sys.stderr)
            for c, n in cats.most_common(args.top):
                print(f"  {n:>5}  {c}", file=sys.stderr)
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    # Accept part numbers as argv, from a file, or from stdin (one per line).
    pns: list[str] = list(args.part_numbers)
    if args.input:
        text, failures = _read_inputs(args.input)
        _die_on_failure(failures)
        pns.extend(_part_numbers_from_text(text))

    matches = lookup_many(pns)
    rows = [m.as_dict() for m in matches.values()]

    if args.unmatched_only:
        rows = [r for r in rows if r["vendor"] is None]
    _write_rows(rows, args.format, sys.stdout)

    if args.summary and rows:
        matched = sum(1 for r in rows if r["vendor"])
        print(
            f"\n{len(rows)} part numbers, {matched} matched "
            f"({matched / len(rows) * 100:.1f}%)",
            file=sys.stderr,
        )
    return 0


# Column names that mark a row as a header rather than a part number.
_HEADER_TOKENS = frozenset(
    """
    pn part partnumber part_number mpn manufacturer_part_number
    model partno part_no 型号 料号 料號 器件 型号料号
    count qty quantity brand vendor category
    """.split()
)


def _part_numbers_from_text(text: str) -> list[str]:
    """Pull part numbers out of a CSV or plain-text list.

    A BOM file normally starts with a header row (``pn,count``). Reading it
    literally would resolve the literal string "pn" as a part number, so
    header rows are detected and skipped.
    """
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # First field of the line — a BOM lists the part number first.
        token = line.split(",")[0].split("\t")[0].strip().strip('"').strip("'")
        if not token:
            continue
        if token.lower().replace(" ", "_") in _HEADER_TOKENS:
            continue
        out.append(token)
    return out


def cmd_vendors(args: argparse.Namespace) -> int:
    if args.audit:
        corpus: list[str] = []
        if args.corpus:
            # _read_inputs takes a list of paths; a bare string would be
            # iterated character by character and every character would be
            # treated as a filename.
            text, failures = _read_inputs([args.corpus])
            _die_on_failure(failures)
            corpus = [normalise(x) for x in text.split()]
        print(report(corpus))
        return 0

    names = vendor_names()
    if args.format == "json":
        json.dump(list(names), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for name in names:
            print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chipnum",
        description="Extract, normalise and classify semiconductor part numbers.",
    )
    parser.add_argument("--version", action="version", version=f"chipnum {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_format(p):
        p.add_argument(
            "--format",
            choices=("csv", "json"),
            default="csv",
            help="output format (default: csv)",
        )

    p_extract = sub.add_parser("extract", help="pull part numbers out of free text")
    p_extract.add_argument("inputs", nargs="*", default=["-"], help="files, or - for stdin")
    p_extract.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="minimum score to keep; raise for precision, lower for recall (default: 5.0)",
    )
    p_extract.add_argument(
        "--unmatched",
        action="store_true",
        help="also emit candidates with no vendor match (for auditing)",
    )
    p_extract.add_argument("--summary", action="store_true", help="print stats to stderr")
    p_extract.add_argument("--top", type=int, default=15, help="rows in the summary (default: 15)")
    add_format(p_extract)
    p_extract.set_defaults(func=cmd_extract)

    p_lookup = sub.add_parser("lookup", help="resolve part numbers to vendor and category")
    p_lookup.add_argument("part_numbers", nargs="*", help="part numbers to resolve")
    p_lookup.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="FILE",
        help="file with one part number per line, or - for stdin; repeatable",
    )
    p_lookup.add_argument("--summary", action="store_true", help="print stats to stderr")
    p_lookup.add_argument("--unmatched-only", action="store_true", help="only print unknowns")
    add_format(p_lookup)
    p_lookup.set_defaults(func=cmd_lookup)

    p_vendors = sub.add_parser("vendors", help="list or audit the vendor table")
    p_vendors.add_argument("--audit", action="store_true", help="report table defects")
    p_vendors.add_argument("--corpus", help="corpus file for shadow detection")
    add_format(p_vendors)
    p_vendors.set_defaults(func=cmd_vendors)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except _InputError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())