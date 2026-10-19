#!/usr/bin/env python3
"""
tests/test_marker_layer.py — 标记层反转的集成测试（依赖 output/ 既有产物作 fixture）

运行：python -m unittest discover tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

ANNOTATION = {
    "quotes": [
        {"file": "示例.txt", "text": "旧神已死，新神未生，我将立法。",
         "source_guess": "自引", "function": "宣言", "judgement": "完整主谓结构",
         "interpretation": "全篇思想纲领"},
    ],
    "emphasis_quotes": [],
    "discipline_plan": {
        "core_disciplines": ["psychology", "linguistics"],
        "secondary_disciplines": ["literary_studies"],
        "excluded_disciplines": [],
        "reasons": {"linguistics": "人称/时态是镜面对话核心信号"},
        "evidence": {"linguistics": ["人称", "时态"]},
    },
}

FIXTURES = ["files_manifest.json", "stats.json", "keywords.json",
            "timeline.json", "quotes.json"]


def fixture_ok():
    out = ROOT / "output"
    return all((out / f).exists() for f in FIXTURES) and (ROOT / "knowledge" / "disciplines.yaml").exists()


def run_script(name, *args):
    return subprocess.run([PY, str(ROOT / "scripts" / name), *args],
                          capture_output=True, text=True)


class TestQuotesMarkerLayer(unittest.TestCase):
    def test_annotation_path_marked(self):
        if not fixture_ok():
            self.skipTest("output/ fixture 缺失")
        out = ROOT / "output"
        with tempfile.TemporaryDirectory() as d:
            ann = Path(d) / "annotation.json"
            ann.write_text(json.dumps(ANNOTATION, ensure_ascii=False), encoding="utf-8")
            r = run_script("quotes.py", "--manifest", str(out / "files_manifest.json"),
                           "--out", d, "--config", str(ROOT / "config.yaml"),
                           "--annotation", str(ann))
            self.assertEqual(r.returncode, 0, r.stderr)
            q = json.loads(Path(d, "quotes.json").read_text(encoding="utf-8"))
            self.assertIn("LLM 标记层", q["method"]["judgement"])
            self.assertEqual(q["total_quotes"], 1)

    def test_legacy_path_marked(self):
        if not fixture_ok():
            self.skipTest("output/ fixture 缺失")
        out = ROOT / "output"
        with tempfile.TemporaryDirectory() as d:
            r = run_script("quotes.py", "--manifest", str(out / "files_manifest.json"),
                           "--out", d, "--config", str(ROOT / "config.yaml"))
            self.assertEqual(r.returncode, 0, r.stderr)
            q = json.loads(Path(d, "quotes.json").read_text(encoding="utf-8"))
            self.assertIn("legacy 启发式", q["method"]["judgement"])


class TestDisciplineRouterMarkerLayer(unittest.TestCase):
    def test_linguistics_in_core(self):
        if not fixture_ok():
            self.skipTest("output/ fixture 缺失")
        out = ROOT / "output"
        with tempfile.TemporaryDirectory() as d:
            ann = Path(d) / "annotation.json"
            ann.write_text(json.dumps(ANNOTATION, ensure_ascii=False), encoding="utf-8")
            r = run_script("discipline_router.py",
                           "--manifest", str(out / "files_manifest.json"),
                           "--stats", str(out / "stats.json"),
                           "--keywords", str(out / "keywords.json"),
                           "--quotes", str(out / "quotes.json"),
                           "--timeline", str(out / "timeline.json"),
                           "--disciplines", str(ROOT / "knowledge" / "disciplines.yaml"),
                           "--out", d, "--annotation", str(ann))
            self.assertEqual(r.returncode, 0, r.stderr)
            plan = json.loads(Path(d, "discipline_plan.json").read_text(encoding="utf-8"))
            self.assertIn("linguistics", plan["core_disciplines"])
            self.assertIn("LLM 标记层", plan["method"])

    def test_legacy_path_avg_cutoff(self):
        if not fixture_ok():
            self.skipTest("output/ fixture 缺失")
        out = ROOT / "output"
        with tempfile.TemporaryDirectory() as d:
            r = run_script("discipline_router.py",
                           "--manifest", str(out / "files_manifest.json"),
                           "--stats", str(out / "stats.json"),
                           "--keywords", str(out / "keywords.json"),
                           "--quotes", str(out / "quotes.json"),
                           "--timeline", str(out / "timeline.json"),
                           "--disciplines", str(ROOT / "knowledge" / "disciplines.yaml"),
                           "--out", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            plan = json.loads(Path(d, "discipline_plan.json").read_text(encoding="utf-8"))
            self.assertIn("legacy 启发式", plan["method"])


if __name__ == "__main__":
    unittest.main()
