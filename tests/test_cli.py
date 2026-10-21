"""CLI tests.

These exercise the command line the way a user does, through ``main()``,
rather than by calling the internals. Several bugs here were only found by
running the real command — an argument that iterated its own string
character by character, a summary that divided by zero on an empty result.
"""

import csv
import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest

from chipnum.cli import main


def run(*argv):
    """Run the CLI and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestLookup:
    def test_inline_part_numbers(self):
        code, out, _ = run("lookup", "STM32G491RET6", "IRFP9140NPBF")
        assert code == 0
        rows = list(csv.DictReader(io.StringIO(out)))
        assert len(rows) == 2
        assert rows[0]["vendor"] == "STMicroelectronics"

    def test_json_output(self):
        code, out, _ = run("lookup", "STM32G491RET6", "--format", "json")
        assert code == 0
        data = json.loads(out)
        assert data[0]["pn"] == "STM32G491RET6"
        assert data[0]["confidence"] == "high"

    def test_input_file(self, tmp_path):
        bom = tmp_path / "bom.csv"
        bom.write_text(
            "pn,count\nSTM32G491RET6,10\nIRFP9140NPBF,5\n", encoding="utf-8"
        )
        code, out, _ = run("lookup", "--input", str(bom))
        assert code == 0
        rows = list(csv.DictReader(io.StringIO(out)))
        assert len(rows) == 2

    def test_input_file_is_a_path_not_a_string(self, tmp_path):
        """--input must take a path, never iterate over it character by
        character. This is a regression test: the option once had no
        ``action``, so a filename was split into single characters."""
        bom = tmp_path / "bom.csv"
        bom.write_text("pn\nSTM32G491RET6\n", encoding="utf-8")
        code, out, err = run("lookup", "--input", str(bom))
        assert code == 0
        assert "cannot read" not in err
        assert len(list(csv.DictReader(io.StringIO(out)))) == 1

    def test_multiple_input_files(self, tmp_path):
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text("pn\nSTM32G491RET6\n", encoding="utf-8")
        b.write_text("pn\nIRFP9140NPBF\n", encoding="utf-8")
        code, out, _ = run("lookup", "--input", str(a), "--input", str(b))
        assert code == 0
        assert len(list(csv.DictReader(io.StringIO(out)))) == 2

    def test_missing_file_exits_nonzero(self, tmp_path):
        code, out, err = run("lookup", "--input", str(tmp_path / "nope.csv"))
        assert code == 2
        assert "cannot read" in err

    def test_unmatched_only(self):
        code, out, _ = run("lookup", "STM32G491RET6", "ZZZ9999QQQ", "--unmatched-only")
        rows = list(csv.DictReader(io.StringIO(out)))
        assert len(rows) == 1
        assert rows[0]["vendor"] == ""

    def test_summary(self):
        code, out, err = run("lookup", "STM32G491RET6", "--summary")
        assert code == 0
        assert "1 part numbers" in err

    def test_no_input_is_not_a_crash(self):
        code, out, err = run("lookup")
        assert code == 0
        assert out.strip() == ""


class TestExtract:
    def test_from_file(self, tmp_path):
        doc = tmp_path / "a.md"
        doc.write_text(
            "NXP 的 FS32K144HAT0MLHT 降价了，TI 的 LMX9838SB 也紧张。", encoding="utf-8"
        )
        code, out, _ = run("extract", str(doc))
        assert code == 0
        rows = list(csv.DictReader(io.StringIO(out)))
        pns = {r["pn"] for r in rows}
        assert "FS32K144HAT0MLHT" in pns
        assert "LMX9838SB" in pns

    def test_summary(self, tmp_path):
        doc = tmp_path / "a.md"
        doc.write_text("STM32G491RET6 和 LMX9838SB", encoding="utf-8")
        code, out, err = run("extract", str(doc), "--summary")
        assert code == 0
        assert "2 unique candidates" in err

    def test_summary_with_no_candidates_does_not_divide_by_zero(self, tmp_path):
        doc = tmp_path / "a.md"
        doc.write_text("今天天气不错。", encoding="utf-8")
        code, out, err = run("extract", str(doc), "--summary")
        assert code == 0
        assert "no candidates" in err

    def test_missing_file_exits_nonzero(self, tmp_path):
        code, out, err = run("extract", str(tmp_path / "nope.md"))
        assert code == 2

    def test_threshold_filters(self, tmp_path):
        doc = tmp_path / "a.md"
        doc.write_text("STM32G491RET6", encoding="utf-8")
        code, out, _ = run("extract", str(doc), "--threshold", "99")
        assert code == 0
        assert out.strip() == ""

    def test_unmatched_flag(self, tmp_path):
        doc = tmp_path / "a.md"
        doc.write_text("ZQX9876PLB 是一个料号", encoding="utf-8")
        code, out, _ = run("extract", str(doc), "--unmatched", "--threshold", "0")
        rows = list(csv.DictReader(io.StringIO(out)))
        assert any(r["pn"] == "ZQX9876PLB" for r in rows)


class TestVendors:
    def test_list(self):
        code, out, _ = run("vendors")
        assert code == 0
        assert "Texas Instruments" in out

    def test_json(self):
        code, out, _ = run("vendors", "--format", "json")
        assert code == 0
        assert "Texas Instruments" in json.loads(out)

    def test_audit(self):
        code, out, _ = run("vendors", "--audit")
        assert code == 0
        assert "prefix collisions" in out

    def test_audit_with_corpus(self, tmp_path):
        corpus = tmp_path / "c.txt"
        corpus.write_text("STM32G491RET6\nLMX9838SB\n", encoding="utf-8")
        code, out, _ = run("vendors", "--audit", "--corpus", str(corpus))
        assert code == 0
        assert "shadowed on corpus" in out


class TestParser:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        assert "chipnum" in capsys.readouterr().out

    def test_no_subcommand_is_an_error(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code != 0
