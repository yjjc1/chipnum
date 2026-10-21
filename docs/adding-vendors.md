# Adding vendors and prefixes

The vendor table is **data**. Adding or correcting a vendor never requires
touching Python.

## Where the table lives

```
src/chipnum/data/
  vendors.toml         hand-curated core table
  vendors_mining.toml  families found by mining real corpora
```

Both files are concatenated at import time. A vendor name may appear in
either file — prefixes **merge** rather than override. So to extend an
existing vendor you can either edit its block or append a new block with the
same `name`.

## Format

```toml
[[vendor]]
name = "Texas Instruments"          # canonical name, shown in output
aliases = ["TI", "德州仪器", "德州"]  # user-facing names that resolve to it
prefixes = [
  { p = "TMS", cat = "dsp" },
  { p = "TPS", cat = "power" },
  { p = "TMP", cat = "analog" },
]
```

| field | meaning |
|---|---|
| `name` | canonical vendor name; appears in every output row |
| `aliases` | alternative spellings users type; resolved by `resolve_vendor()` |
| `p` | the prefix, matched case-insensitively against the start of the part number |
| `cat` | category id from `categories.py` |

## The rules, and why

**1. Never a prefix shorter than three characters.**

Two-character prefixes are weak evidence. They only match when nothing
longer does, and they are reported as `low` confidence — but they still
swallow real parts. `IP` once claimed Infineon's `IPD50N06S2L`; `ML` claimed
Melexis's `MLX90614`; `SP` claimed Infineon's `SPW47N60C3`.

Two-character prefixes that already exist (`ST`, `AD`, `TL`, `LM`, `LT`, `MC`)
are tolerated because they name famous, unambiguous series. Do not add more
without a strong reason.

**2. Prefer the specific family over the series.**

`LM3` matches TI's `LM358`; `LM3S` does not. `AD` matches a lot; `ADUM`
does not.

**3. Verify against real samples.**

A prefix that matches nothing real is a guess. Add the real part numbers it
matches to `tests/test_corpus.py` and to `GROUND_TRUTH` in
`tests/test_vendors.py`.

**4. Do not add company names as prefixes.**

`TI` and `NXP` are brand mentions, not part numbers. The extractor filters
those, but a brand prefix in the table reintroduces the problem.

**5. Use a category from the taxonomy.**

Categories live in `src/chipnum/categories.py`. A new category needs a new
entry there; `tests/test_corpus.py` fails on an unknown category id.

## After editing

```console
python -m chipnum.audit          # collisions and weak prefixes
pytest                           # the corpus integrity tests
chipnum lookup <your part number>
```

`python -m chipnum.audit` reports:

- **collisions** — one vendor's prefix is a strict prefix of another's. With
  longest-match this is not automatically wrong, but each is a place where a
  future edit could go wrong.
- **shadowing** — a part number in your corpus is claimed by a shorter
  prefix than the longest one available. This is a live bug.
- **over-generic** — prefixes short enough to be ambiguous with ordinary
  English.

## Quick reference: which vendor makes which part

| you have | it is probably | add |
|---|---|---|
| `STM32...` | ST | `STM32` |
| `TL...` | TI | `TL` |
| `AD...` | Analog Devices | `AD8`, `ADM`, `ADUM` |
| `LTC...` | Analog Devices | `LTC` |
| `MAX...` | Analog Devices | `MAX` |
| `FS32...` | NXP | `FS32` |
| `S32K...` | NXP | `S32K` |
| `PIC...` | Microchip | `PIC` |
| `ATMEGA...` | Microchip | `ATMEGA` |
| `IRF...` | Infineon | `IRF` |
| `BSS...` | Infineon / Nexperia | `BSS` |
| `W25Q...` | Winbond | `W25Q` |
| `MT40...` | Micron | `MT40` |
| `GRM...` | Murata | `GRM` |
| `XC7...` | Xilinx | `XC7` |
| `nRF...` | Nordic | `nRF` |

This table is a starting point, not the whole story — check the real part's
datasheet before adding a prefix.
