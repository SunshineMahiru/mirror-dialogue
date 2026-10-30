import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import timeline  # noqa: E402


class TestDates(unittest.TestCase):
    def test_dotted_full_date(self):
        self.assertEqual(timeline.extract_date("2020.12.23"), "2020-12-23")

    def test_year_month(self):
        self.assertEqual(timeline.extract_date("——2020.10"), "2020-10")

    def test_normalize_frontmatter(self):
        self.assertEqual(timeline.normalize_date("2020年10月1日 12:00"), "2020-10-01")


class TestTimeSlots(unittest.TestCase):
    def test_pre_dawn_is_late_night(self):
        self.assertEqual(timeline.detect_time_slot("凌晨三点"), "深夜")

    def test_morning(self):
        self.assertEqual(timeline.detect_time_slot("早上"), "清晨")


class TestSeasons(unittest.TestCase):
    def test_youth_is_not_spring(self):
        self.assertEqual(timeline.detect_season("青春"), [])

    def test_november_is_autumn_only(self):
        self.assertEqual(timeline.detect_season("十一月"), ["秋"])

    def test_winter_word(self):
        self.assertEqual(timeline.detect_season("寒冷的冬天"), ["冬"])


class TestSentiment(unittest.TestCase):
    def test_negation(self):
        score, _ = timeline.sentiment_score("我不快乐")
        self.assertLess(score, 0)

    def test_no_double_count(self):
        score, _ = timeline.sentiment_score("疲惫不堪")
        self.assertEqual(score, -1.0)


if __name__ == "__main__":
    unittest.main()
