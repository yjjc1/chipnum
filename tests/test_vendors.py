"""Vendor resolution tests.

The cases here are hand-verified ground truth. Each one corresponds to a real
mistake found while building the vendor table — a misattributed part number
is worse than an unresolved one, because downstream BOM and sourcing
decisions inherit the error.
"""

import pytest

from chipnum.vendors import lookup, lookup_many, resolve_vendor, vendor_names

# (part number, expected vendor) — every one checked by hand against the
# vendor's own part-numbering documentation.
GROUND_TRUTH = [
    ("STM32G491RET6", "STMicroelectronics"),
    ("L7805ABV", "STMicroelectronics"),
    ("TL072CDR", "Texas Instruments"),
    ("LMX9838SB", "Texas Instruments"),
    ("TMP117AIDRVR", "Texas Instruments"),
    ("TM4C123GH6PZI7R", "Texas Instruments"),
    ("MSP430F149IPMR", "Texas Instruments"),
    ("FS32K144HAT0MLHT", "NXP Semiconductors"),
    ("U74LVC1G125G-AL5-R", "NXP Semiconductors"),
    ("ADUC848BSZ62-5", "Analog Devices"),
    ("W25Q40CLWI", "Winbond Electronics"),
    ("W988D6FBGX6I", "Winbond Electronics"),
    ("MT40A512M16TD-062E", "Micron Technology"),
    ("MT48LC16M16A2P-6A", "Micron Technology"),
    ("M471A5244CB0-CRC", "Micron Technology"),
    ("BTS724G", "Infineon Technologies"),
    ("IRS2092STRPBF", "Infineon Technologies"),
    ("IRFP9140NPBF", "Infineon Technologies"),
    ("AT24C32D-SSHM-T", "Microchip Technology"),
    ("XC7A200T-2FFG1156I", "AMD Xilinx"),
    ("XC2V1000-4FG256I", "AMD Xilinx"),
    ("GRM188R71C105KA64D", "Murata Manufacturing"),
    ("GCM1555C1H100JA16J", "Murata Manufacturing"),
    ("TMK105ABJ474KV-F", "Murata Manufacturing"),
    ("RTL8153BI-CG", "Realtek"),
    ("GD32F303CCT6", "GigaDevice"),
    ("ESP32-WROOM-32", "Espressif Systems"),
    ("nRF52840-QIAA", "Nordic Semiconductor"),
    ("M25P80-VMW6TG", "Macronix"),
]


@pytest.mark.parametrize("pn,expected", GROUND_TRUTH)
def test_ground_truth(pn, expected):
    assert lookup(pn).vendor == expected


class TestSpecificity:
    """Longer, more specific prefixes must beat shorter generic ones."""

    def test_tmp_over_tm(self):
        # TMP117 is a TI temperature sensor. A bare "TM" prefix once claimed it
        # for a display driver vendor.
        assert lookup("TMP117").vendor == "Texas Instruments"

    def test_tm4_over_tm(self):
        assert lookup("TM4C123").vendor == "Texas Instruments"

    def test_tmk_not_display_driver(self):
        assert lookup("TMK107").vendor == "Murata Manufacturing"

    def test_memory_not_soc(self):
        # M471... is Micron DRAM; "M4" style SoC prefixes once claimed it.
        assert lookup("M471A5244CB0-CRC").vendor == "Micron Technology"

    def test_spi_flash_not_soc(self):
        assert lookup("M25P80-VMW6TG").vendor == "Macronix"


class TestCaseHandling:
    def test_lowercase_input(self):
        assert lookup("stm32f103c8t6").vendor == "STMicroelectronics"

    def test_case_significant_prefix(self):
        # nRF keeps its lowercase 'n'; normalise() upper-cases, so lookup must
        # also try the original casing.
        assert lookup("nRF52840").vendor == "Nordic Semiconductor"

    def test_mixed_case_input(self):
        assert lookup("NrF52840").vendor == "Nordic Semiconductor"


class TestUnmatched:
    def test_unknown_reports_none(self):
        m = lookup("ZZZ-NOT-A-PART-9999")
        assert m.vendor is None
        assert m.category == "unknown"
        assert not m.matched

    def test_empty_input(self):
        assert lookup("").vendor is None

    def test_does_not_raise_on_junk(self):
        for junk in ("!!!!", "----", "12345678", "a" * 200):
            assert lookup(junk).vendor is None or isinstance(lookup(junk).vendor, str)


class TestConfidence:
    """A two-character prefix is weak evidence and must be labelled as such."""

    def test_specific_prefix_is_high_confidence(self):
        m = lookup("STM32G491RET6")
        assert m.vendor == "STMicroelectronics"
        assert m.confidence == "high"

    def test_two_letter_prefix_is_low_confidence(self):
        m = lookup("LM358")  # TI's LM series, matched on two characters
        assert m.vendor == "Texas Instruments"
        assert m.confidence == "low"

    def test_specific_prefix_beats_two_letter(self):
        # IPD50N06S2L is an Infineon OptiMOS. A two-letter "IP" prefix once
        # claimed it for a different vendor; the specific prefix must win.
        m = lookup("IPD50N06S2L-13")
        assert m.vendor == "Infineon Technologies"
        assert m.confidence == "high"

    def test_mlx_is_melexis_not_rohm(self):
        # MLX90614 is a Melexis IR sensor. ROHM's two-letter "ML" once won.
        m = lookup("MLX90614")
        assert m.vendor == "Melexis"
        assert m.confidence == "high"

    def test_lm358_not_st(self):
        # ST's "LM3" prefix once shadowed TI's LM series.
        assert lookup("LM358").vendor == "Texas Instruments"

    def test_st_lm3_still_st(self):
        assert lookup("LM3S811").vendor == "STMicroelectronics"

    def test_ltm_is_analog_devices_not_ti(self):
        # LTM is Linear Technology's uModule line (now ADI). TI's generic
        # "LT" prefix used to claim it.
        assert lookup("LTM4644IY").vendor == "Analog Devices"
        assert lookup("LTM4700IY").vendor == "Analog Devices"

    def test_ltc_is_analog_devices(self):
        assert lookup("LTC2411IMS").vendor == "Analog Devices"

    def test_lt1_line_is_ti(self):
        # TI holds the LT1xxx line; Linear Technology holds LTC/LTM/LT3/LT8.
        assert lookup("LT1765ES8").vendor == "Texas Instruments"

    def test_lontium_lt_family(self):
        # Lontium's LT86xx/LT97xx are USB-C and display-bridge controllers,
        # not Analog Devices parts.
        assert lookup("LT8611EXA").vendor == "Lontium Semiconductor"
        assert lookup("LT8641UXE").vendor == "Lontium Semiconductor"

    def test_conexant_cx_family_is_narrow(self):
        # The generic "CX" prefix also matched CXD2826 and CXDB4CBAM, which
        # are not Conexant parts.
        assert lookup("CX20706-21Z").vendor == "Conexant"
        assert lookup("CXD2826ER").vendor != "Conexant"

    def test_unmatched_has_no_confidence(self):
        assert lookup("ZZZ-9999-QQQ").confidence == "none"


class TestCategoryLabels:
    def test_mcu(self):
        assert lookup("STM32G491RET6").category == "mcu"

    def test_memory(self):
        assert lookup("W25Q40CLWI").category == "memory"

    def test_category_label(self):
        assert lookup("STM32G491RET6").category_label == "Microcontroller"


class TestBatch:
    def test_deduplicates(self):
        m = lookup_many(["stm32f103", "STM32F103", " STM32-F103 "])
        # Case and surrounding whitespace collapse to one key; the hyphenated
        # spelling is a genuinely different canonical form.
        assert len(m) == 2
        assert all(x.vendor == "STMicroelectronics" for x in m.values())

    def test_empty(self):
        assert lookup_many([]) == {}


class TestVendorRegistry:
    def test_names_are_non_empty(self):
        names = vendor_names()
        assert len(names) > 50
        assert all(isinstance(n, str) and n for n in names)

    def test_resolve_alias(self):
        assert resolve_vendor("TI") == "Texas Instruments"
        assert resolve_vendor("ti") == "Texas Instruments"
        assert resolve_vendor("德州仪器") == "Texas Instruments"

    def test_resolve_unknown(self):
        assert resolve_vendor("Not A Vendor") is None