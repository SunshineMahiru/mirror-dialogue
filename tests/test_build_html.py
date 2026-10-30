import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def write_min(tmp: Path, gate_report=None):
    stats = {
        "files": [],
        "global": {
            "total_files": 1,
            "total_chinese_chars": 1,
            "total_paragraphs": 1,
            "total_sentences": 1,
        },
    }
    quotes = {
        "total_quotes": 0,
        "total_emphasis_quotes": 0,
        "density": 0,
        "quotes": [],
        "emphasis_quotes": [],
    }
    (tmp / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
    (tmp / "quotes.json").write_text(json.dumps(quotes, ensure_ascii=False), encoding="utf-8")
    if gate_report is not None:
        (tmp / "validation_report.json").write_text(
            json.dumps(gate_report, ensure_ascii=False), encoding="utf-8")


def build(tmp: Path, *args):
    return subprocess.run(
        [PY, str(ROOT / "scripts" / "build_html.py"),
         "--data-dir", str(tmp), "--out", str(tmp / "report.html"),
         "--template", str(ROOT / "templates" / "report.html.j2"), *args],
        capture_output=True, text=True)


class TestBuildStatus(unittest.TestCase):
    def test_no_gate_report_marks_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            write_min(tmp)
            r = build(tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = (tmp / "report.html").read_text(encoding="utf-8")
            self.assertIn("未运行事前闸门校验", html)

    def test_failed_gate_with_force_marks_draft(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            write_min(tmp, {"pass": [], "fail": ["示例失败"], "warn": []})
            r = build(tmp, "--force")
            self.assertEqual(r.returncode, 0, r.stderr)
            html = (tmp / "report.html").read_text(encoding="utf-8")
            self.assertIn("不合格草稿", html)
            self.assertIn("示例失败", html)


if __name__ == "__main__":
    unittest.main()
