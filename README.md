# chipnum

**Extract, normalise and classify semiconductor part numbers from free text.**

`chipnum` pulls manufacturer part numbers (MPNs) out of prose, tables, CSV
cells and BOM files, normalises the spellings people actually type, and
resolves each one to a vendor and a component category.

```console
$ chipnum extract articles.md --summary
29 unique candidates, 29 vendor-matched (100.0%)

top vendors:
      3  NXP Semiconductors
      3  Infineon Technologies
      3  STMicroelectronics
...
```

---

## Why this exists

Part numbers are written by humans, in prose, in every conceivable spelling:
`stm32f103c8t6`, `STM32-F103`, `STM32 F103`, `ＳＴＭ３２Ｆ１０３`. A BOM
column, a WeChat article about chip shortages, and a distributor's quote all
spell the same die differently.

Existing tools generally assume you already have a clean, delimited list. The
hard part — pulling MPNs out of running text and knowing which vendor a
prefix belongs to — is left to the user.

`chipnum` does that part, and it tells you when it is unsure.

**Design rule: reporting "unknown" is correct. Confidently naming the wrong
vendor is not.** A wrong vendor propagates into sourcing decisions, so
matches carry a confidence level and short prefixes are never allowed to
outrank specific ones.

---

## Install

```console
pip install chipnum
```

No runtime dependencies. Python 3.10+.

From source:

```console
git clone https://github.com/OWNER/chipnum.git
cd chipnum
pip install -e ".[dev]"
```

---

## Usage

### Extract from text

```console
chipnum extract article.md
chipnum extract *.csv --format json > parts.json
cat article.md | chipnum extract -
```

Output is CSV with one row per unique part number:

| column | meaning |
|---|---|
| `raw` | the token exactly as it appeared in the source |
| `pn` | the normalised form |
| `score` | confidence score; higher is more certain |
| `vendor` | resolved vendor, or empty if unknown |
| `category` | component category id |
| `reasons` | which signals produced the score |

### Resolve a BOM

```console
chipnum lookup --input bom.csv --summary
chipnum lookup STM32G491RET6 LMX9838SB IRFP9140NPBF
chipnum lookup --input bom.csv --unmatched-only   # only the unknowns
```

```
pn,vendor,category,category_label,confidence
STM32G491RET6,STMicroelectronics,mcu,Microcontroller,high
LMX9838SB,Texas Instruments,analog,Analog / Mixed-signal,high
IRFP9140NPBF,Infineon Technologies,discrete,Discrete Semiconductor,high
```

### Audit the vendor table

```console
chipnum vendors --audit
chipnum vendors --audit --corpus partnumbers.txt
```

Reports prefix collisions, over-generic prefixes, and any part number in a
corpus that a shorter prefix is stealing from a more specific one.

### As a library

```python
import chipnum

chipnum.lookup("stm32f103c8t6").vendor
# 'STMicroelectronics'

for cand in chipnum.extract("今天 STM32G491RET6 交期又延长了"):
    print(cand.pn, cand.vendor, cand.score)
```

---

## How it works

```
text → normalise → score → vendor lookup → confidence
```

**Normalise** (`chipnum/normalize.py`) — NFKC-folds the text so full-width
`ＳＴＭ３２` becomes `STM32`, strips invisible characters, upper-cases,
canonicalises separators, and trims punctuation that copy-paste picks up at
the edges. A space between two runs is treated as a separator, not deleted —
otherwise `STM32 F103` and `STM32_F103` would canonicalise differently
depending on which separator the author typed.

**Score** (`chipnum/extract.py`) — every candidate gets a score from
independent signals: vendor-prefix match, alphanumeric mixing, length band,
hyphenation, and penalties for prose words and implausible shapes. The score
is a sum rather than a rule cascade so that `reasons` can explain *why*
something was accepted, which is what makes the threshold tunable instead of
guesswork.

**Resolve** (`chipnum/vendors.py`) — longest prefix wins, matched against a
data-driven table in `data/*.toml`. Adding a vendor is a data edit, never a
code change.

### Confidence

| level | meaning |
|---|---|
| `high` | matched on a prefix of three characters or more |
| `low` | matched on a two-character prefix — weak evidence, verify before use |
| `none` | no vendor claimed it |

A two-character prefix may **never** outrank a longer one. This is not
cosmetic: without that rule, `IPD50N06S2L` (an Infineon OptiMOS) is claimed by
a generic `IP` prefix, `MLX90614` (a Melexis IR sensor) is called ROHM, and
`FC32K146UAT0VLLR` (NXP) is called a Quectel module. Each of those was a real
misattribution found while building the table.

---

## Vendor table

99 vendors across 28 categories, in `src/chipnum/data/`:

- `vendors.toml` — the hand-curated core table
- `vendors_mining.toml` — families found by mining a real corpus

Both files are concatenated at import time, and a vendor name may appear in
either — prefixes merge rather than override. See
[docs/adding-vendors.md](docs/adding-vendors.md).

### Rules for adding a prefix

1. **Never a prefix shorter than three characters.** Two-letter prefixes are
   the main precision risk; `ST`, `AD` and `TL` are tolerable because they are
   famous, `IP` and `ML` were not.
2. **Verify against real samples.** A prefix that matches nothing real is
   just a guess.
3. **Prefer the specific family over the series.** Use `LM3S` rather than
   `LM3`, `ADUM` rather than `AD`.
4. **Re-run the audit** after every edit: `chipnum vendors --audit`.

---

## Precision

The table was built against a corpus of 7,441 unique part numbers extracted
from 5,415 Chinese-language semiconductor industry articles (2016–2026):

| | count | share |
|---|---:|---:|
| part numbers in corpus | 7,441 | 100% |
| resolved to a vendor | 4,265 | 57.3% |
| — high confidence | 3,568 | 48.0% |
| — low confidence | 697 | 9.4% |
| left unresolved | 3,176 | 42.7% |

Roughly 43% of the corpus is passive components, connectors, inductors,
modules and unbranded parts that no vendor-prefix table can resolve. They are
reported as unresolved rather than guessed at.

On a hand-checked set of 29 part numbers spanning every major vendor family,
resolution is 29/29.

The corpus is not redistributed with this package. `tests/test_corpus.py`
carries a checked subset.

---

## Development

```console
pip install -e ".[dev]"
pytest              # 158 tests
ruff check .
python -m chipnum.audit
```

### Layout

```
src/chipnum/
  normalize.py    text → canonical part number
  extract.py      text → scored candidates
  vendors.py      part number → vendor, category, confidence
  categories.py   the category taxonomy
  audit.py        vendor-table integrity checks
  cli.py          command-line interface
  data/*.toml     the vendor table
```

---

## Contributing

Issues and pull requests are welcome — especially **vendor prefix corrections**.
If chipnum names the wrong vendor for a part number, open an issue with the
part number and the correct vendor; that is the most valuable contribution
this project can receive.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).
