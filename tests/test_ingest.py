import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ingest  # noqa: E402


CFG = {
    "strip_frontmatter": True,
    "strip_html_tags": True,
    "strip_page_numbers": True,
    "collapse_blank_lines": True,
}


class TestCleanText(unittest.TestCase):
    def test_prose_block_kept(self):
        text = "---\n标题\n正文第一段\n---\n后文"
        self.assertEqual(ingest.clean_text(text, CFG), text)

    def test_frontmatter_stripped(self):
        text = "---\ndate: 2020-10-01\ntitle: x\n---\n正文"
        self.assertEqual(ingest.clean_text(text, CFG), "正文")

    def test_numeric_lines_kept(self):
        text = "日记标题\n2020\n今天下雨。\n3"
        self.assertEqual(ingest.clean_text(text, CFG), text)

    def test_page_number_removed(self):
        text = "正文\n第 2 页\n后文"
        self.assertEqual(ingest.clean_text(text, CFG), "正文\n后文")


class TestPrivacy(unittest.TestCase):
    def test_name_and_phone_masked(self):
        cfg = {
            "privacy_mode": True,
            "privacy_names": ["张三"],
            "privacy_addresses": [],
            "privacy_patterns": [{"name": "手机号", "pattern": r"1[3-9]\d{9}"}],
        }
        out = ingest.apply_privacy("张三 13800138000", cfg)
        self.assertNotIn("张三", out)
        self.assertNotIn("13800138000", out)

    def test_invalid_pattern_raises(self):
        with self.assertRaises(ValueError):
            ingest.compile_privacy_patterns(
                {"privacy_patterns": [{"pattern": "("}]})


class TestScan(unittest.TestCase):
    def test_case_insensitive_and_excludes_out(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "out").mkdir()
            (root / "a.MD").write_text("x", encoding="utf-8")
            (root / "b.txt").write_text("x", encoding="utf-8")
            (root / "out" / "c.md").write_text("x", encoding="utf-8")
            cfg = {"supported_extensions": [".md", ".txt"]}
            names = {p.name for p in ingest.scan(root, cfg, exclude_dirs=[root / "out"])}
            self.assertIn("a.MD", names)
            self.assertIn("b.txt", names)
            self.assertNotIn("c.md", names)


if __name__ == "__main__":
    unittest.main()
