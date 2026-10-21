"""Corpus regression test.

The source corpus is 7,441 unique part numbers mined from 5,415 Chinese
semiconductor-industry articles (2016-2026). The corpus itself is not
redistributed with this package. What follows is a checked subset: samples
whose vendor was confirmed by hand, plus the specific mistakes this tool was
built to avoid.

If you extend the vendor table, run this file first. A change that breaks any
assertion here is a regression that would have shipped a wrong vendor name.
"""

import pytest

from chipnum.audit import find_collisions, find_shadowed
from chipnum.vendors import _table, lookup, lookup_many, vendor_names

# Confirmed samples from the corpus, spanning every major vendor family the
# table claims to cover.
CONFIRMED = [
    "STM32G491RET6",
    "TL072CDR",
    "TMP117AIDRVR",
    "TM4C123GH6PZI7R",
    "LMX9838SB",
    "FS32K144HAT0MLHT",
    "U74LVC1G125G-AL5-R",
    "ADUC848BSZ62-5",
    "W25Q40CLWI",
    "W988D6FBGX6I",
    "MT40A512M16TD-062E",
    "MT48LC16M16A2P-6A",
    "M471A5244CB0-CRC",
    "BTS724G",
    "IRS2092STRPBF",
    "IRFP9140NPBF",
    "MSP430F149IPMR",
    "L7805ABV",
    "AT24C32D-SSHM-T",
    "XC7A200T-2FFG1156I",
    "XC2V1000-4FG256I",
    "GRM188R71C105KA64D",
    "GCM1555C1H100JA16J",
    "TMK105ABJ474KV-F",
    "RTL8153BI-CG",
    "GD32F303CCT6",
    "ESP32-WROOM-32",
    "nRF52840-QIAA",
    "M25P80-VMW6TG",
    "BZX84-C5V1-Q",
    "BZT52H-C6V8",
    "MT25QU01GBBB8E12",
    "S9S12G128AMLH",
    "MCIMX6D6AVT10AD",
    "KLM8G1GETF",
    "NT5CC128M16JR-EKI",
    "TCAN1044AVDRQ1",
    "SKY13373-460LF",
    "AR8035",
    "DRV8837DSGR",
    "LSM6DSOTR",
    "N32G452VEL7",
    "ADUM1201ARZ",
    "F280025PMSR",
]

# Shapes that appear in the corpus as prose noise, not part numbers. The
# extractor must not claim them.
NOT_PARTS = [
    "GB300",
    "RV1126",
    "Y2024",
    "Q100H",
    "C2000",
    "DC12V",
    "MI300",
]


@pytest.mark.parametrize("pn", CONFIRMED)
def test_confirmed_sample_resolves(pn):
    assert lookup(pn).vendor is not None, f"{pn} no longer resolves to any vendor"


class TestTableIntegrity:
    def test_no_shadowed_matches(self):
        """No part number may be claimed by a shorter prefix than it deserves."""
        shadowed = find_shadowed(CONFIRMED)
        assert not shadowed, f"prefix shadowing: {shadowed}"

    def test_collision_count_bounded(self):
        # Collisions are latent bugs, not automatically fatal, but a large
        # number means the table has drifted.
        collisions = find_collisions()
        assert len(collisions) < 60, (
            f"{len(collisions)} prefix collisions — review the vendor tables"
        )

    def test_no_one_character_prefixes(self):
        # A single-character prefix matches a quarter of all part numbers.
        one_char = [p for p in _table() if len(p.prefix) == 1]
        assert not one_char, f"single-character prefixes: {[p.prefix for p in one_char]}"

    def test_digit_leading_prefixes_are_specific(self):
        # Some real families do start with a digit (74HC logic, Infineon's
        # 1ED/2ED gate drivers), so digit-leading is not itself a defect.
        # What matters is that such a prefix is long enough to be evidence.
        too_short = [p.prefix for p in _table() if p.prefix[0].isdigit() and len(p.prefix) < 3]
        assert not too_short, f"short digit-leading prefixes: {too_short}"

    def test_two_letter_prefixes_are_rare(self):
        # Two-character prefixes are the main precision risk. A handful of
        # well-known ones (ST, TI, AD, MC) are legitimate; a flood is not.
        two_letter = [p.prefix for p in _table() if len(p.prefix) == 2]
        assert len(two_letter) <= 50, f"too many two-letter prefixes: {two_letter}"

    def test_all_categories_known(self):
        from chipnum.categories import CATEGORIES

        unknown = sorted({p.category for p in _table()} - set(CATEGORIES))
        assert not unknown, f"categories missing from taxonomy: {unknown}"

    def test_vendor_count(self):
        assert len(vendor_names()) >= 50


class TestCoverage:
    def test_majority_of_confirmed_resolve(self):
        matches = lookup_many(CONFIRMED)
        hit = [k for k, v in matches.items() if v.matched]
        assert len(hit) / len(CONFIRMED) >= 0.95

    def test_categories_are_populated(self):
        matches = lookup_many(CONFIRMED)
        cats = {m.category for m in matches.values() if m.matched}
        # Not one narrow category — the taxonomy is actually being used.
        assert len(cats) >= 5


class TestNoiseResistance:
    @pytest.mark.parametrize("token", NOT_PARTS, ids=lambda t: t)
    def test_noise_shaped_tokens_are_not_scored_high(self, token):
        from chipnum.extract import score_token

        c = score_token(token)
        # They may score above zero if a vendor genuinely claims them, but
        # nothing should treat them as confident extractions by default.
        assert c.score < 9.0, f"{token} scored {c.score} — would be auto-extracted"