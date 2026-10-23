import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import validate as V  # noqa: E402


def new_report():
    return {"pass": [], "fail": [], "warn": [], "schema": {}}


class TestMirrorDialogueChapter(unittest.TestCase):
    """专章字段名写成 mirror_dialogue_overview 时模板匹配不到，会渲染出一段空白。"""

    def test_wrong_field_name_fails(self):
        r = new_report()
        ga = {"mirror_dialogue_overview": {"common_addressee": []}}
        V.check_mirror_dialogue_chapter(ga, r)
        self.assertTrue(any("mirror_dialogue_chapter: 缺失" in f for f in r["fail"]))

    def test_missing_part_fails(self):
        r = new_report()
        ga = {"mirror_dialogue_chapter": {"addressee_spectrum": []}}
        V.check_mirror_dialogue_chapter(ga, r)
        self.assertTrue(any("缺五部分" in f for f in r["fail"]))

    def test_correct_field_passes(self):
        r = new_report()
        mdc = {
            "addressee_spectrum": [{"addressee": "过去的我", "frequency": 3,
                                    "intensity": "高", "evidence": "镜" * 10}],
            "self_naming_timeline": [{"file": "a", "stage": "我→他",
                                      "description": "镜", "evidence": "镜"}],
            "self_talk_patterns": {"judgment": [], "comfort": [],
                                   "inquiry": [], "alternation": "镜"},
            "silence_archaeology": [{"cue": "省略号", "location": "第1段", "unsaid": "镜"}],
            "dialogue_ethics": "镜" * 1600,
        }
        V.check_mirror_dialogue_chapter({"mirror_dialogue_chapter": mdc}, r)
        self.assertFalse(any("mirror_dialogue_chapter" in f for f in r["fail"]))


class TestCrossDisciplineMulti(unittest.TestCase):
    """多元解释或综合模型缺失时，跨学科综合只剩目录上的一个标题。"""

    def test_missing_multi_explanations_fails(self):
        r = new_report()
        V.check_cross_discipline_multi({"consensus": []}, r)
        self.assertTrue(any("multi_explanations" in f for f in r["fail"]))
        self.assertTrue(any("synthesis_model" in f for f in r["fail"]))
        self.assertTrue(any("complementary" in f for f in r["fail"]))
        self.assertTrue(any("limitations_ethics" in f for f in r["fail"]))

    def test_enough_multi_explanations_passes(self):
        r = new_report()
        cross = {
            "multi_explanations": [{"phenomenon": "p", "explanations": []}] * 8,
            "synthesis_model": [{"phenomenon": "x"}],
            "complementary": ["x"],
            "limitations_ethics": ["x"],
        }
        V.check_cross_discipline_multi(cross, r)
        self.assertFalse(any("multi_explanations" in f or "synthesis_model" in f
                             for f in r["fail"]))


class TestSingleMirrorFields(unittest.TestCase):
    """字段名写错时，代词指认与自我称谓变化会在报告里悄悄消失。"""

    def test_missing_pronoun_map_fails(self):
        r = new_report()
        single = [{"file": "a.txt", "mirror_dialogue": {"pronouns": {}}}]
        V.check_single_mirror_fields(single, r)
        self.assertTrue(any("pronoun_map" in f for f in r["fail"]))


class TestVerifySwitch(unittest.TestCase):
    """离线时无从核验，如实标注「未检索」算不得编造。"""

    def test_verify_off_warns_not_fails(self):
        r = new_report()
        discipline = [{"discipline": "psychology", "references": [
            {"author": "A", "title": "T", "year": "2000", "verified": False}]}]
        plan = {"core_disciplines": ["psychology"]}
        V.check_references_verified(discipline, plan, r, verify_on=False)
        self.assertFalse(any(x.startswith("references:") for x in r["fail"]))
        self.assertTrue(any(x.startswith("references:") for x in r["warn"]))

    def test_verify_on_fails(self):
        r = new_report()
        discipline = [{"discipline": "psychology", "references": [
            {"author": "A", "title": "T", "year": "2000", "verified": False}]}]
        plan = {"core_disciplines": ["psychology"]}
        V.check_references_verified(discipline, plan, r, verify_on=True)
        self.assertTrue(any(x.startswith("references:") for x in r["fail"]))


class TestGateOnlyExitCode(unittest.TestCase):
    """内容空泛的产物必须在渲染前被拦住，否则交付的是一份没人愿意读的报告。"""

    def test_gate_blocks_shallow_output(self):
        with tempfile.TemporaryDirectory() as d:
            # 结构齐全、内容单薄的产物
            shallow_single = [{
                "file": "a.txt", "title": "a", "date_guess": "",
                "summary": "太短",
                "mirror_dialogue": {"pronouns": {}},
                "quotes": [],
            }]
            Path(d, "single_analysis.json").write_text(
                json.dumps(shallow_single, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(ROOT / "validate.py"),
                 "--data-dir", d, "--config", str(ROOT / "config.yaml"),
                 "--gate-only"],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, "浅产物应被闸门拦截（exit 1）")

    def test_gate_passes_deep_output(self):
        # 单篇内容达标后，闸门不应再报 depth 与字段缺失
        with tempfile.TemporaryDirectory() as d:
            deep_single = [{
                "file": "a.txt", "title": "a", "date_guess": "",
                "summary": "镜" * 1200,
                "mirror_dialogue": {
                    "addressee": "过去的我", "addressee_trajectory": "我→他",
                    "pronoun_map": [{"pronoun": "我", "referent": "自己", "example": "镜", "position": "1"}],
                    "self_naming_change": [{"from": "我", "to": "他", "meaning": "客体化", "example": "镜", "position": "1"}],
                    "self_talk": [{"type": "审判", "scene": "镜", "example": "镜", "position": "1"}],
                    "unsaid": "镜" * 500,
                },
                "quotes": [{"text": "镜" * 20, "position": "第1段", "interpretation": "镜"}] * 5,
            }]
            Path(d, "single_analysis.json").write_text(
                json.dumps(deep_single, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(ROOT / "validate.py"),
                 "--data-dir", d, "--config", str(ROOT / "config.yaml"),
                 "--gate-only"],
                capture_output=True, text=True)
            # 其余 JSON 缺失仍会 exit 1，这条用例只关心 depth 与字段两类 fail
            self.assertNotIn("depth:", r.stdout + r.stderr, "深度达标后不应再有 depth fail")
            self.assertNotIn("mirror_dialogue: a.txt 缺字段", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
