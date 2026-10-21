# Design notes

Why the code is shaped the way it is. Most of this exists because an earlier
version was wrong in a specific, findable way.

## The pipeline

```
raw text
  │
  ├─ normalise()   → canonical form, one spelling per die
  │
  ├─ extract()     → candidates, each with a score and a reason list
  │
  └─ lookup()      → vendor, category, confidence
```

Each stage is independently testable, and the boundaries are where the bugs
were.

## Normalisation

**NFKC first.** Chinese text and copy-paste routinely produce full-width
forms: `ＳＴＭ３２` instead of `STM32`. NFKC folds them, and also folds
full-width hyphens (`－`) into ASCII ones, so the separator rules apply
uniformly.

**Whitespace is a separator, not a deletion.** An early version stripped all
whitespace, so `STM32 F103` became `STM32F103` while `STM32_F103` became
`STM32-F103`. The same die had two canonical forms depending on which
separator the author typed. Now whitespace goes through the separator rule
like any other, and all spellings converge on `STM32-F103`.

**Separators are preserved in the canonical form, removed in the fuzzy form.**
`STM32-F103` and `STM32F103` are the same part; the hyphen carries no
information for matching but does for display. So `normalise()` keeps it and
`compact()` drops it, and deduplication uses `compact()`.

**Case is folded, except where it is meaningful.** `stm32f103` and
`STM32F103` are the same die. But `nRF` is a brand's own spelling, and
`iNAND` is SanDisk's. `lookup()` therefore also tries the original text and
a case-insensitive pass, so `nRF52840` resolves to Nordic rather than
falling through to nothing.

## Extraction

**Scores are additive, not a rule cascade.** Every signal contributes a
number, and `reasons` records which ones fired. A cascade makes the
behaviour impossible to tune: you cannot raise the threshold and predict what
you lose. With additive scores, raising the threshold drops the weakest
evidence first, which is what you want.

**Negative signals matter as much as positive ones.** "APPLE" is a vendor
name; "SPI" and "I2C" are interface names; "Q3" is a quarter. A token that
merely *looks* like a part number is not one. The stopword and prose lists
are small and specific on purpose — a large blunt list would suppress real
parts whose series names collide with English words.

**The default threshold is conservative.** A false positive costs a user
more trust than a missed part costs coverage, because the tool's job is to
be believed. `--threshold` exposes the dial for callers who want recall
instead.

## Vendor resolution

**Longest prefix wins.** This is the whole game. `STM32F103` must resolve via
`STM32`, not `ST`.

**Two-character prefixes may never outrank longer ones.** This rule was
added after the corpus showed real misattributions:

| part number | wrong answer | correct |
|---|---|---|
| `IPD50N06S2L-13` | Injoinic (`IP`) | Infineon |
| `MLX90614` | ROHM (`ML`) | Melexis |
| `SPW47N60C3` | ST (`SP`) | Infineon |
| `FC32K146UAT0VLLR` | Quectel (`FC`) | NXP |
| `DSPIC30F2010-30I` | TI (`DS`) | Microchip |
| `BLM21PG221SN1D` | Belling (`BL`) | Murata |
| `GRT188R60J226ME13D` | Goodix (`GR`) | Murata |
| `LM358` | ST (`LM3`) | TI |

Resolution therefore runs in two passes — prefixes of three or more
characters first, two-character prefixes only as a fallback. The fallback
still produces an answer, but it is labelled `low` confidence, and the
extractor penalises it, so weak matches sort below strong ones and can be
filtered out.

**The table is data.** `data/*.toml` holds prefixes; `vendors.py` holds no
vendor names. Adding a vendor or correcting a prefix is a data edit. This
matters because the table is the part that gets maintained by people who are
not the original author — and by automated mining over corpora.

**A package code may be stripped, but only as a last resort.** `U74LVC1G125G`
is an NXP 74LVC part in a TSSOP package; the leading `U` is packaging, not
a vendor. This is tried only after a direct match fails, so a genuine vendor
whose name starts with one of those letters is never displaced.

## Confidence

The tool distinguishes three states, and the distinction is the point:

- **high** — matched on a specific prefix. Trust it.
- **low** — matched on a two-character prefix. Verify before use.
- **none** — no vendor claimed it.

Reporting "unknown" is a correct answer. A confidently wrong vendor is not,
because it propagates into sourcing decisions downstream — a BOM importer
that trusts a wrong vendor will order the wrong die.

## What is deliberately absent

- **No fuzzy matching (edit distance).** "LM358" and "LMX9838SB" are
  different parts. Edit-distance matching would happily merge them.
- **No price, stock or availability data.** Out of scope, and it would rot
  immediately.
- **No dependency on the internet.** A part number table that cannot be
  resolved offline cannot be used in an air-gapped sourcing workflow.
- **No inference from part-number structure.** "Does this look like an
  STM32?" is already answered by the prefix. Guessing from letter patterns
  would be unfalsifiable.

## The audit

`chipnum.audit` exists because the vendor table is data and data rots. It
reports three classes of defect:

- **collision** — one vendor's prefix is a strict prefix of another's. With
  longest-match this is not automatically wrong, but each one is a place
  where a future edit could go wrong.
- **shadowing** — on a real corpus, a part number is claimed by a shorter
  prefix than the longest one available. This is an actual live bug, and
  the test suite fails on it.
- **over-generic** — prefixes short enough to be ambiguous with ordinary
  English. Reported for review, not automatically removed.
