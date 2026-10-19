#!/usr/bin/env python3
"""
run.py — 编排入口：五阶段串联全流程

四层边界（见 SKILL.md / methodology/README.md）：
- 方法论层（methodology/）：定义规则。
- 标记层（LLM）：通读原文产出 annotation.json（引用候选 + 学科路由判定）。
- 计算层（脚本）：只做精确计算（统计 / 引用定位计数 / 证据命中计数）。
- 分析层（LLM）：基于标记层+计算层产出 4 个分析 JSON。

五阶段：
  阶段1 ingest → stats → timeline（纯计算，脚本）
  阶段2 annotation.json（标记层，LLM）
  阶段3 quotes(定位计数) → discipline_router(证据计数) → knowledge_lookup（脚本）
  阶段4 single / global / discipline / cross 四个分析 JSON（LLM）
  阶段5 build_html（build 前自动跑 validate.py 事前闸门；--force 可出草稿）

运行方式：
    python run.py --target-dir <目录> [--out ./output] [--config ./config.yaml] \
        [--disciplines ./knowledge/disciplines.yaml] \
        [--template ./templates/report.html.j2] \
        [--knowledge-source builtin] [--html ./output/report.html] \
        [--run-llm-check] [--force] [--skip-scripts]

- 不带 --skip-scripts：跑阶段1，检查 annotation.json 缺失则打印待办退出，存在则继续阶段3。
- 带 --skip-scripts：跳过脚本（沿用已有产物），只检查分析 JSON 并 build（断点续跑）。
- 事前闸门：build 前强制跑 validate.py --gate-only，fail 非空默认拒绝渲染，--force 可出草稿。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# 由 LLM 生成、build_html 消费的分析 JSON
LLM_JSON = [
    "single_analysis.json",
    "global_analysis.json",
    "discipline_analysis.json",
    "cross_discipline.json",
]


def run(cmd):
    print(f"\n[run] {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent))
    if r.returncode != 0:
        print(f"[error] 命令失败: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(r.returncode)


def run_gate(data_dir, config_path):
    """build 前的事前闸门：跑 validate.py --gate-only，返回 exit code。

    - 0 表示内容检查全部通过；
    - 非 0 表示存在 fail（深度不足/文献未核验/隐私泄露等），由调用方决定拦截或 --force。
    """
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "validate.py"),
           "--data-dir", data_dir, "--config", config_path, "--gate-only"]
    print(f"\n[gate] {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(root))
    return r.returncode


def run_post_check(data_dir, config_path, html_path):
    """build 后的完整自检（含 HTML 结构），仅输出结果、不阻塞流程。"""
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "validate.py"),
           "--data-dir", data_dir, "--config", config_path, "--html", html_path]
    print(f"\n[validate] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(root))


def gen_concepts_json(disciplines_path, out_dir):
    """从 disciplines.yaml 提取所有学科概念，生成 knowledge_lookup 所需 concepts.json。"""
    if yaml is None:
        print("[warn] PyYAML 未安装，跳过 concepts.json 生成", file=sys.stderr)
        return None
    with open(disciplines_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    disciplines = []
    for d in data.get("disciplines", []):
        concepts = []
        for c in d.get("concepts", []):
            concepts.append(c if isinstance(c, str) else c.get("name", ""))
        disciplines.append({"id": d.get("id"), "name": d.get("name"), "concepts": concepts})
    path = Path(out_dir) / "concepts.json"
    path.write_text(json.dumps({"disciplines": disciplines}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", required=True)
    ap.add_argument("--out", default="./output")
    ap.add_argument("--config", default="./config.yaml")
    ap.add_argument("--disciplines", default="./knowledge/disciplines.yaml")
    ap.add_argument("--template", default="./templates/report.html.j2")
    ap.add_argument("--knowledge-source", default="builtin", choices=["network", "local", "builtin"])
    ap.add_argument("--local-dir", default="./knowledge/references")
    ap.add_argument("--html", default="",
                    help="HTML 输出路径；留空则写到 --out 目录下的 report.html")
    ap.add_argument("--run-llm-check", action="store_true",
                    help="若 LLM JSON 齐全则继续 build_html")
    ap.add_argument("--force", action="store_true",
                    help="事前闸门有 fail 时仍强制渲染 HTML（页面标注「不合格草稿」）")
    ap.add_argument("--skip-scripts", action="store_true",
                    help="跳过全部脚本（阶段1+阶段3），直接检查分析 JSON 并 build_html（纯 build 模式）")
    ap.add_argument("--skip-stage1", action="store_true",
                    help="只跳过阶段1（ingest/stats/timeline），仍会跑阶段3（quotes/discipline_router，"
                         "读 annotation.json）；用于生成 annotation 后断点续跑")
    args = ap.parse_args()

    out = args.out
    manifest = f"{out}/files_manifest.json"
    html_path = args.html or f"{out}/report.html"

    if args.skip_scripts:
        print("[run] 已跳过全部脚本步骤（--skip-scripts），沿用已有产物。")
    else:
        # ============ 阶段1：纯计算脚本（不依赖标记层） ============
        if args.skip_stage1:
            print("[run] 跳过阶段1（--skip-stage1），沿用 ingest/stats/timeline 产物。")
        else:
            # 1. 扫描解析
            run([sys.executable, str(SCRIPTS_DIR / "ingest.py"),
                 "--target-dir", args.target_dir, "--out", out, "--config", args.config])

            # 2. 统计
            run([sys.executable, str(SCRIPTS_DIR / "stats.py"),
                 "--manifest", manifest, "--out", out, "--config", args.config])

            # 3. 时间线（只依赖 manifest，纯计算）
            run([sys.executable, str(SCRIPTS_DIR / "timeline.py"),
                 "--manifest", manifest, "--out", out])

        # ============ 阶段2：标记层（LLM 产物，判定交给 LLM） ============
        annotation_path = f"{out}/annotation.json"
        if not Path(annotation_path).exists():
            print("\n[待办] 标记层 annotation.json 缺失。")
            print("       请 LLM 通读原文，按 prompts/annotate.md 产出标记层：")
            print("       - quotes[]：判定「什么算引用」（含来源/功能/依据）")
            print("       - discipline_plan：判定学科路由（core/secondary/excluded + 依据）")
            print(f"       写入 {annotation_path} 后重跑：")
            print(f"      python run.py --target-dir {args.target_dir} --skip-stage1")
            sys.exit(0)

        # ============ 阶段3：依赖标记层的脚本（只做精确计算/证据计数） ============
        # 4. 引用：脚本只定位/计数，不再自行判定「什么算引用」
        run([sys.executable, str(SCRIPTS_DIR / "quotes.py"),
             "--manifest", manifest, "--out", out, "--config", args.config,
             "--annotation", annotation_path])

        # 5. 学科路由：脚本只做证据命中计数，core/secondary 判定来自标记层
        run([sys.executable, str(SCRIPTS_DIR / "discipline_router.py"),
             "--manifest", manifest,
             "--stats", f"{out}/stats.json",
             "--keywords", f"{out}/keywords.json",
             "--quotes", f"{out}/quotes.json",
             "--timeline", f"{out}/timeline.json",
             "--disciplines", args.disciplines, "--out", out,
             "--annotation", annotation_path])

        # 6. 知识来源记录（concepts 由 disciplines.yaml 生成）
        concepts = gen_concepts_json(args.disciplines, out)
        if concepts:
            run([sys.executable, str(SCRIPTS_DIR / "knowledge_lookup.py"),
                 "--concepts", str(concepts),
                 "--source", args.knowledge_source,
                 "--local-dir", args.local_dir, "--out", out])
        else:
            print("[warn] PyYAML 缺失，无法生成 concepts.json，knowledge_lookup 被跳过；",
                  "knowledge_sources.json 将缺失，validate.py 会据此报 fail（exit 1）。",
                  file=sys.stderr)

    # 7. 检查 LLM 生成的 JSON 是否齐全
    missing = [j for j in LLM_JSON if not (Path(out) / j).exists()]
    if missing:
        print("\n[待办] 以下分析 JSON 需由 LLM 按 SKILL.md 分批生成：")
        for j in missing:
            print(f"  - {j}")
        print("提示：单篇 Map 每批 3-5 篇（见 config.yaml chunk_batch），")
        print("      逐学科分析按 discipline_plan.json 的 core 学科逐个产出。")
        print("      生成后重新运行：")
        print(f"      python run.py --target-dir {args.target_dir} --run-llm-check --skip-scripts")
        sys.exit(0)

    # 8. 生成 HTML（LLM JSON 齐全时）
    if args.run_llm_check:
        # P0：build 前强制跑事前闸门（内容检查，跳过 HTML）
        gate_rc = run_gate(out, args.config)
        if gate_rc != 0 and not args.force:
            print("\n[闸门] validate.py 检测到 fail，已拒绝渲染 HTML。")
            print("       请按上方 [FAIL] 清单修复（补齐深度 / 核验文献 / 修隐私等）后重跑；")
            print("       或追加 --force 强制生成「不合格草稿」。")
            sys.exit(1)
        build_cmd = [sys.executable, str(SCRIPTS_DIR / "build_html.py"),
                     "--data-dir", out, "--out", html_path, "--template", args.template]
        if args.force:
            build_cmd.append("--force")
        run(build_cmd)
        # build 后跑完整 validate（含 HTML 结构），输出最终 validation_report.json
        run_post_check(out, args.config, html_path)
    else:
        print("\n[完成] 脚本统计步骤已全部完成；LLM 分析 JSON 已齐，")
        print("       如需生成 HTML，追加 --run-llm-check --skip-scripts 重跑（不重算脚本）。")


if __name__ == "__main__":
    main()
