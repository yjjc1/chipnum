"""Extraction tests, using real Chinese-language industry prose.

The prose fixtures are excerpts from Chinese semiconductor-industry articles
of the kind chipnum exists to process: part numbers embedded mid-sentence,
inside table rows, with punctuation and OCR noise around them.
"""

from chipnum.extract import extract, extract_unique, score_token

PROSE = """
NXP（恩智浦）的一颗MCU FS32K144HAT0MLHT已经平稳降价数月并回到2位数的市场价。
另一边，一线厂交期延长到至少半年，其中 STM32G491RET6 和 TM4C123GH6PZI7R 最紧张。
安世 BUK9K17-60EX 现货充足，TI 的 LMX9838SB 也开始放量。
Infineon IRFP9140NPBF 与 IRS2092STRPBF 都是老面孔，价格反而在跌。
"""

TABLE = """
品牌,型号,年份,数量
安世,BUK9K17-60EX,22+无外盒 全标,100K
安世,74AHC1G32GV-Q100,22+,21K
ST,STM32G491RET6,LQFP64,10K
Micron,MT40A512M16TD-062E,FBGA-96,5K
"""


class TestExtractFromProse:
    def test_finds_embedded_parts(self):
        pns = {c.pn for c in extract(PROSE)}
        for expected in ("FS32K144HAT0MLHT", "STM32G491RET6", "LMX9838SB", "IRFP9140NPBF"):
            assert expected in pns

    def test_attaches_vendor(self):
        by_pn = {c.pn: c for c in extract(PROSE)}
        assert by_pn["STM32G491RET6"].vendor == "STMicroelectronics"
        assert by_pn["LMX9838SB"].vendor == "Texas Instruments"

    def test_does_not_match_chinese_prose(self):
        # Chinese words with no alphanumerics must never become candidates.
        for c in extract(PROSE):
            assert c.pn.isascii(), f"non-ASCII candidate: {c.pn!r}"


class TestExtractFromTable:
    def test_finds_all_rows(self):
        pns = {c.pn for c in extract(TABLE)}
        assert "BUK9K17-60EX" in pns
        assert "74AHC1G32GV-Q100" in pns
        assert "MT40A512M16TD-062E" in pns

    def test_strips_csv_commas(self):
        pns = {c.pn for c in extract(TABLE)}
        # The trailing comma of "BUK9K17-60EX," must not survive.
        assert not any(p.endswith(",") for p in pns)


class TestPrecision:
    def test_rejects_company_names(self):
        # "NXP" and "Infineon" are vendor names, not part numbers.
        pns = {c.pn for c in extract(PROSE)}
        assert "NXP" not in pns
        assert "INFINEON" not in pns

    def test_rejects_generic_prose_words(self):
        pns = {c.pn for c in extract(
            "The MOSFET gate driver supports SPI and I2C interfaces at high frequency."
        )}
        assert "MOSFET" not in pns
        assert "SPI" not in pns
        assert "I2C" not in pns

    def test_rejects_years_and_prices(self):
        cands = extract("2024 revenue was USD 1200 in Q3 2025.")
        for c in cands:
            assert not c.pn.isdigit()

    def test_unmatched_excluded_by_default(self):
        # A well-shaped token that no vendor claims is withheld unless asked.
        cands = extract("the part ZQX9876 is not in our table")
        assert all(c.matched for c in cands)

    def test_unmatched_available_on_request(self):
        cands = extract(
            "the part ZQX9876 is not in our table",
            include_unmatched=True,
            threshold=0.0,
        )
        assert any(c.pn == "ZQX9876" for c in cands)


class TestDedupe:
    def test_unique_dedupes(self):
        text = "STM32G491RET6 and stm32g491ret6 and STM32-G491RET6"
        cands = extract_unique(text)
        assert len(cands) == 1
        # The hyphenated spelling is a different canonical form but the same
        # die, so it must not survive as a second candidate.
        assert cands[0].pn.replace("-", "") == "STM32G491RET6"

    def test_extract_dedupes_raw_forms(self):
        cands = extract("STM32G491RET6 stm32g491ret6")
        assert len(cands) == 1


class TestScoring:
    def test_vendor_match_scores_high(self):
        matched = score_token("STM32G491RET6")
        unmatched = score_token("ZQX9876PLB")
        assert matched.score > unmatched.score

    def test_reasons_are_recorded(self):
        c = score_token("STM32G491RET6")
        assert any(r.startswith("vendor:") for r in c.reasons)

    def test_stopword_penalised(self):
        assert score_token("APPLE").score < 0

    def test_short_token_penalised(self):
        assert score_token("GB3").score < 5


class TestThreshold:
    def test_higher_threshold_yields_fewer(self):
        text = "the ZQX9876PLB and STM32G491RET6 and ABCD1234EFGH parts"
        low = extract(text, threshold=0.0, include_unmatched=True)
        high = extract(text, threshold=8.0, include_unmatched=True)
        assert len(high) <= len(low)

    def test_default_keeps_vendor_matches(self):
        cands = extract("STM32G491RET6")
        assert len(cands) == 1
        assert cands[0].matched


class TestEdgeCases:
    def test_empty_text(self):
        assert extract("") == []

    def test_none_text(self):
        assert extract(None) == []

    def test_very_long_token_bounded(self):
        assert extract("A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8") == []

    def test_pure_punctuation(self):
        assert extract("--- ,,, ;;;") == []