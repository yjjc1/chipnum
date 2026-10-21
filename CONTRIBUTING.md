# Contributing to chipnum

Thanks for helping. The most valuable contribution is a **vendor correction**:
if chipnum names the wrong vendor for a part number, that is a bug that
directly causes wrong answers for users, and fixing it is the best thing you
can send.

## Reporting a wrong vendor

Open an issue with:

1. The part number, exactly as it appears (including any hyphens).
2. The correct vendor.
3. The correct category, if you know it.

Or send a pull request that fixes the prefix table directly — see below.

## Changing the vendor table

The table lives in `src/chipnum/data/`. It is data, not code: **adding a
vendor never requires touching Python.**

- `vendors.toml` — the hand-curated core table
- `vendors_mining.toml` — families found by mining real corpora

Both files are concatenated at import time. A vendor name may appear in
either file; prefixes merge rather than override. So to add a prefix to an
existing vendor, either edit its existing block or append a new block with
the same `name`.

```toml
[[vendor]]
name = "Texas Instruments"
aliases = ["TI", "德州仪器"]
prefixes = [
  { p = "TMP", cat = "analog" },
  { p = "TM4", cat = "mcu" },
]
```

### The rules, and why they exist

These are not style preferences. Each one exists because breaking it has
already produced a wrong answer.

**1. Never add a prefix shorter than three characters.**

Two-character prefixes are weak evidence and are handled differently: they
only match when nothing longer does, and they are reported as `low`
confidence. But a two-character prefix still swallows real parts. `IP` once
claimed Infineon's `IPD50N06S2L`; `ML` claimed Melexis's `MLX90614`.

Two-character prefixes that already exist (`ST`, `AD`, `TL`, `LM`, `LT`, …)
are tolerated because they name famous, unambiguous series. Do not add more
without a strong reason.

**2. Prefer the specific family over the series.**

Use `LM3S`, not `LM3` — `LM3` also matched TI's `LM358`. Use `ADUM`, not
`AD`. Use `ADUM` for a specific family only when you can name the family.

**3. Verify against real samples.**

A prefix that matches nothing real is a guess. If you add one, include the
real part numbers it matches in `tests/test_corpus.py`.

**4. Do not add prefixes that are company names.**

`TI`, `NXP`, `ST` as a *brand mention* are not part numbers. The extractor
already filters those, but a brand prefix in the table reintroduces the
problem.

**5. Re-run the audit after every edit.**

```console
python -m chipnum.audit
```

It reports prefix collisions, over-generic prefixes, and any part number
where a shorter prefix is stealing from a longer one. A non-zero collision
count is expected — the check is that you have not *added* to it blindly.

## Adding a test

Every vendor correction should come with a test. Add the part number to
`GROUND_TRUTH` in `tests/test_vendors.py`:

```python
("IPD50N06S2L-13", "Infineon Technologies"),
```

and to `CONFIRMED` in `tests/test_corpus.py` if it comes from the corpus.

## Running the tests

```console
pip install -e ".[dev]"
pytest
ruff check .
```

The suite must pass before you open a pull request. If you changed the
vendor table, the corpus integrity tests are the ones that will catch an
over-broad prefix.

## Style

- Python 3.10+, `ruff` for linting, 100-character lines.
- Docstrings explain *why*, not *what*.
- No runtime dependencies. The package must stay installable with nothing
  but the standard library.

## Licence

By contributing you agree that your contributions are licensed under the
MIT licence, the same as the project.
