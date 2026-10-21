"""Normalisation tests."""

from chipnum.normalize import (
    compact,
    is_plausible,
    normalise,
    split_suffix,
)


class TestNormalise:
    def test_uppercases(self):
        assert normalise("stm32f103c8t6") == "STM32F103C8T6"

    def test_strips_surrounding_whitespace(self):
        assert normalise("  LM358  ") == "LM358"

    def test_strips_edge_punctuation(self):
        assert normalise("LMX9838SB,") == "LMX9838SB"
        assert normalise("(IRFP9140NPBF)") == "IRFP9140NPBF"
        assert normalise("。TPS5430。") == "TPS5430"

    def test_folds_fullwidth(self):
        # Chinese text and copy-paste routinely produce full-width forms.
        assert normalise("ＳＴＭ３２") == "STM32"
        assert normalise("ＴＬ０７２") == "TL072"

    def test_folds_fullwidth_hyphen(self):
        assert normalise("STM32－F103") == "STM32-F103"

    def test_canonicalises_internal_separators(self):
        assert normalise("STM32_F103") == "STM32-F103"
        assert normalise("STM32 F103") == "STM32-F103"
        assert normalise("STM32/F103") == "STM32-F103"

    def test_preserves_significant_hyphen(self):
        # The hyphen in STM32-F103 separates family from line, and dropping
        # it would change the part number.
        assert normalise("STM32-F103") == "STM32-F103"

    def test_removes_zero_width(self):
        assert normalise("STM32\u200bF103") == "STM32F103"

    def test_empty_and_none(self):
        assert normalise("") == ""
        assert normalise(None) == ""

    def test_real_corpus_samples(self):
        # Drawn from a 7,441-part-number corpus of industry articles.
        for raw in ("BTS724G", "W25Q40CLWI", "74AHC1G32GV-Q100", "XC7A200T-2FFG1156I"):
            assert normalise(raw) == raw


class TestCompact:
    def test_drops_separators(self):
        assert compact("LMX-9838SB") == "LMX9838SB"
        assert compact("LMX9838SB") == "LMX9838SB"

    def test_two_spellings_collapse(self):
        # Vendors disagree about hyphenation; fuzzy matching must not.
        assert compact("STM32-F103") == compact("STM32F103")

    def test_preserves_case_insensitivity(self):
        assert compact("stm32f103") == compact("STM32-F103")


class TestSplitSuffix:
    def test_no_hyphen(self):
        assert split_suffix("IRFP9140NPBF") == ("IRFP9140NPBF", "")

    def test_splits_at_last_hyphen(self):
        assert split_suffix("XC7A200T-2FFG1156I") == ("XC7A200T", "2FFG1156I")

    def test_multiple_hyphens(self):
        base, suffix = split_suffix("CGA-AB1-XYZ")
        assert base == "CGA-AB1"
        assert suffix == "XYZ"


class TestIsPlausible:
    def test_accepts_real_parts(self):
        assert is_plausible("STM32F103C8T6")
        assert is_plausible("W25Q40CLWI")

    def test_rejects_pure_digits(self):
        assert not is_plausible("20240115")

    def test_rejects_too_short(self):
        assert not is_plausible("GB3")

    def test_rejects_pure_letters(self):
        assert not is_plausible("ABCDEFGH")

    def test_rejects_too_long(self):
        assert not is_plausible("A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5")