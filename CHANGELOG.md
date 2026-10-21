# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-21

### Added

- Publishing to PyPI on a version tag. The `publish` job authenticates with
  the `PYPI_API_TOKEN` repository secret — the token is never stored in the
  repository — and verifies the built distributions with `twine check`
  before uploading, including an assertion that the vendor table is actually
  packaged in the wheel.
- The PyPI badge and `pip install chipnum` in the README.

## [Unreleased]

### Fixed

- The `LT` prefix was claimed by Texas Instruments, but it is split across
  three vendors: TI holds the LT1xxx line, Linear Technology (now Analog
  Devices) holds LTC/LTM/LTR/LT3/LT4/LT6/LT8x, and Lontium holds the
  LT6911/LT86xx/LT97xx USB-C and display-bridge controllers. The table now
  lists only the specific families each vendor owns, so `LTM4644IY` resolves
  to Analog Devices rather than TI, and `LT8611EXA` resolves to Lontium
  rather than being claimed by a generic prefix. An `LT...` part outside
  those families resolves to no vendor, which is the correct outcome.
- Conexant's generic `CX` prefix also matched `CXD2826` and `CXDB4CBAM`,
  which are not Conexant parts. Narrowed to the `CX1`/`CX2` families.

## [0.2.0] - 2026-10-21

### Added

- `chipnum.identity()` — a stable, documented identity for a part number,
  independent of how it was spelled. Two part numbers that denote the same
  die share a `key` even when written differently (`STM32F103C8T6` vs
  `STM32-F103C8T6`), which is what you join on when merging two BOMs or a
  BOM with a set of articles. `pn` keeps the canonical spelling for display.
- `chipnum identity` subcommand, with `--input`, `--summary` and
  `--format json`.
- `chipnum.fold()` — NFKC-fold and strip invisible characters, without
  touching case or separators. Exposed because it is needed to reason about
  case-significant prefixes such as `nRF`.

### Changed

- The vendor table is now split across `data/vendors.toml` (hand-curated core)
  and `data/vendors_mining.toml` (families found by mining real corpora).
  Both files are concatenated at import time; a vendor name may appear in
  either, and prefixes merge rather than override.
- `Match` and `Identity` now carry a `confidence` field: `high` for a
  three-or-more-character prefix, `low` for a two-character one, `none` for
  no match. Two-character prefixes are now resolved in a second pass, so they
  can never outrank a longer prefix.

### Fixed

- A two-character prefix could outrank a longer, more specific one. This
  produced real misattributions: `IPD50N06S2L` (Infineon OptiMOS) was
  claimed by a generic `IP` prefix, `MLX90614` (Melexis) by ROHM's `ML`,
  `SPW47N60C3` (Infineon) by ST's `SP`, `FC32K146UAT0VLLR` (NXP) by
  Quectel's `FC`, and `DSPIC30F2010-30I` (Microchip) by TI's `DS`. See
  issue #1.
- ST's `LM3` prefix shadowed TI's LM series, so `LM358` resolved to ST.
  Narrowed to `LM3S`/`LM3P`/`LM3L`, which are the real ST families.
- Whitespace was deleted rather than treated as a separator, so `STM32 F103`
  and `STM32_F103` produced two different canonical forms for the same die.
- `nRF`-style case-significant prefixes never resolved, because
  normalisation upper-cases the input.
- `--input` on `chipnum lookup` iterated the filename character by
  character, so every character was treated as a path.
- A BOM's header row (`pn,count`) was resolved as a part number, so the
  literal string `pn` was reported as a Chipown component.
- `chipnum extract --summary` divided by zero on a document with no
  candidates.
- A missing input file exited with an uncaught `SystemExit` instead of
  returning exit code 2 from `main()`.
- `chipnum vendors --audit --corpus` treated the corpus path as a list of
  paths and tried to open each character.

## [0.1.0] - 2026-10-21

### Added

- Initial release.
- `chipnum.extract()` — pull part numbers out of free text, with additive
  scoring so every candidate carries the reasons that produced its score.
- `chipnum.lookup()` — resolve a part number to a vendor and category using
  longest-prefix matching over a data-driven TOML table.
- `chipnum.normalise()` — NFKC folding, separator canonicalisation, edge
  trimming.
- `chipnum.audit` — checks the vendor table for prefix collisions,
  over-generic prefixes and shadowing against a real corpus.
- `chipnum extract`, `chipnum lookup` and `chipnum vendors` subcommands.
- 179 tests, including a hand-checked ground-truth set and a corpus
  regression suite.

[Unreleased]: https://github.com/yjjc1/chipnum/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/yjjc1/chipnum/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yjjc1/chipnum/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yjjc1/chipnum/releases/tag/v0.1.0
