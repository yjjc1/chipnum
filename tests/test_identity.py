"""Tests for the stable-identity API.

Implements the request in issue #2: a documented way to resolve a part
number to an identity that survives spelling changes, so that two lists can
be joined on it.
"""

import pytest

from chipnum import identity


class TestIdentity:
    def test_same_die_different_spellings_share_a_key(self):
        keys = {
            identity("STM32F103C8T6").key,
            identity("stm32f103c8t6").key,
            identity("STM32-F103C8T6").key,
            identity("STM32 F103C8T6").key,
            identity("ＳＴＭ３２Ｆ１０３Ｃ８Ｔ６").key,
        }
        assert len(keys) == 1

    def test_key_is_separator_free(self):
        assert identity("STM32-F103C8T6").key == "STM32F103C8T6"

    def test_pn_keeps_the_canonical_spelling(self):
        # The key is for joining; the pn is for display and stays readable.
        assert identity("stm32 f103c8t6").pn == "STM32-F103C8T6"

    def test_carries_the_vendor(self):
        ident = identity("stm32f103c8t6")
        assert ident.vendor == "STMicroelectronics"
        assert ident.category == "mcu"
        assert ident.confidence == "high"

    def test_different_parts_have_different_keys(self):
        assert identity("STM32F103C8T6").key != identity("LM358").key

    def test_unresolved_part_still_has_an_identity(self):
        # An unknown part number is still the same unknown part number.
        ident = identity("ZZZ9999QQQ")
        assert ident.key == "ZZZ9999QQQ"
        assert ident.vendor is None
        assert ident.confidence == "none"

    def test_empty_input(self):
        assert identity("").key == ""

    def test_as_dict(self):
        d = identity("STM32F103C8T6").as_dict()
        assert set(d) == {"pn", "key", "vendor", "category", "confidence"}
        assert d["key"] == "STM32F103C8T6"

    @pytest.mark.parametrize(
        "a,b",
        [
            ("STM32F103C8T6", "stm32f103c8t6"),
            ("LMX-9838SB", "LMX9838SB"),
            ("IRFP9140NPBF", "irfp9140npbf"),
            ("ADUM1201ARZ", "ADUM-1201ARZ"),
        ],
    )
    def test_pairs(self, a, b):
        assert identity(a).key == identity(b).key
