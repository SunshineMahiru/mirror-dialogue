import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

QUOTE_TEXT = "旧的秩序已经退场，新的秩序尚未生成，我将立法。"

ANNOTATION = {
    "quotes": [
        {"file": "示例.txt", "text": QUOTE_TEXT,
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


def make_fixture(tmp: Path):
    """在临时目录里造一份清单与标记层，测试不再依赖 output/。"""
    manifest = {
        "files": [{
            "file": "示例.txt",
            "name": "示例.txt",
            "content": f"他说“{QUOTE_TEXT}”然后沉默。",
        }]
    }
    manifest_path = tmp / "files_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    annotation_path = tmp / "annotation.json"
    annotation_path.write_text(json.dumps(ANNOTATION, ensure_ascii=False), encoding="utf-8")
    return manifest_path, annotation_path


def run_script(name, *args):
    return subprocess.run([PY, str(ROOT / "scripts" / name), *args],
                          capture_output=True, text=True)


class TestQuotesMarkerLayer(unittest.TestCase):
    def test_annotation_path_marked(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, annotation = make_fixture(tmp)
            r = run_script("quotes.py", "--manifest", str(manifest),
                           "--out", d, "--config", str(ROOT / "config.yaml"),
                           "--annotation", str(annotation))
            self.assertEqual(r.returncode, 0, r.stderr)
            q = json.loads(Path(d, "quotes.json").read_text(encoding="utf-8"))
            self.assertIn("LLM 标记层", q["method"]["judgement"])
            self.assertEqual(q["total_quotes"], 1)

    def test_legacy_path_marked(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, _ = make_fixture(tmp)
            r = run_script("quotes.py", "--manifest", str(manifest),
                           "--out", d, "--config", str(ROOT / "config.yaml"))
            self.assertEqual(r.returncode, 0, r.stderr)
            q = json.loads(Path(d, "quotes.json").read_text(encoding="utf-8"))
            self.assertIn("legacy 启发式", q["method"]["judgement"])

    def test_missing_annotation_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, _ = make_fixture(tmp)
            r = run_script("quotes.py", "--manifest", str(manifest),
                           "--out", d, "--config", str(ROOT / "config.yaml"),
                           "--annotation", str(tmp / "missing.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("annotation 文件不存在", r.stderr)


class TestDisciplineRouterMarkerLayer(unittest.TestCase):
    def test_linguistics_in_core(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, annotation = make_fixture(tmp)
            r = run_script("discipline_router.py",
                           "--manifest", str(manifest),
                           "--disciplines", str(ROOT / "knowledge" / "disciplines.yaml"),
                           "--out", d, "--annotation", str(annotation))
            self.assertEqual(r.returncode, 0, r.stderr)
            plan = json.loads(Path(d, "discipline_plan.json").read_text(encoding="utf-8"))
            self.assertIn("linguistics", plan["core_disciplines"])
            self.assertIn("LLM 标记层", plan["method"])
            self.assertIn("digital_humanities", plan["core_disciplines"])

    def test_legacy_path_avg_cutoff(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, _ = make_fixture(tmp)
            r = run_script("discipline_router.py",
                           "--manifest", str(manifest),
                           "--disciplines", str(ROOT / "knowledge" / "disciplines.yaml"),
                           "--out", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            plan = json.loads(Path(d, "discipline_plan.json").read_text(encoding="utf-8"))
            self.assertIn("legacy 启发式", plan["method"])

    def test_missing_annotation_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, _ = make_fixture(tmp)
            r = run_script("discipline_router.py",
                           "--manifest", str(manifest),
                           "--disciplines", str(ROOT / "knowledge" / "disciplines.yaml"),
                           "--out", d, "--annotation", str(tmp / "missing.json"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("annotation 文件不存在", r.stderr)


if __name__ == "__main__":
    unittest.main()
