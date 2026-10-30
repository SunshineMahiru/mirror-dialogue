import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quotes  # noqa: E402


class TestFindPosition(unittest.TestCase):
    def test_mid_line_quote(self):
        content = "第一段\n第二段有引用。\n第三段"
        self.assertEqual(quotes.find_position(content, "引用"), "第2段")

    def test_line_start_quote(self):
        content = "第一段\n引用在第二段开头。\n第三段"
        self.assertEqual(quotes.find_position(content, "引用"), "第2段")

    def test_blank_lines_are_skipped(self):
        content = "第一段\n\n第二段有引用。\n\n第三段"
        self.assertEqual(quotes.find_position(content, "引用"), "第2段")


if __name__ == "__main__":
    unittest.main()
