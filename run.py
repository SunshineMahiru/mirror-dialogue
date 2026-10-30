import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# 四份分析产物，缺一份就说明分析还没做完
LLM_JSON = [
    "single_analysis.json",
    "global_analysis.json",
    "discipline_analysis.json",
    "cross_discipline.json",
]


def run(cmd):
    printable = " ".join(str(c) for c in cmd)
    print(f"\n[run] {printable}")
    r = subprocess.run([str(c) for c in cmd], cwd=str(Path(__file__).resolve().parent))
    if r.returncode != 0:
        print(f"[error] 命令失败: {printable}", file=sys.stderr)
        sys.exit(r.returncode)


def run_gate(data_dir, config_path):
    """返回 validate.py 闸门的退出码：0 表示内容检查全部通过。"""
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "validate.py"),
           "--data-dir", data_dir, "--config", config_path, "--gate-only"]
    print(f"\n[gate] {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd], cwd=str(root))
    return r.returncode


def run_post_check(data_dir, config_path, html_path):
    """渲染之后补跑一次完整校验，返回退出码供上层决定是否判失败。"""
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "validate.py"),
           "--data-dir", data_dir, "--config", config_path, "--html", html_path]
    print(f"\n[validate] {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd], cwd=str(root))
    return r.returncode


def gen_concepts_json(disciplines_path, out_dir):
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


def load_config(config_path):
    if not Path(config_path).exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_project_path(root: Path, value: str) -> Path:
    """配置里的相对路径按仓库根目录解析，命令行里的相对路径按调用目录解析。"""
    p = Path(value).expanduser()
    return (p if p.is_absolute() else root / p).resolve()


def require_files(paths, hint):
    missing = [str(p) for p in paths if not Path(p).exists()]
    if missing:
        print(f"[error] 缺少前置产物: {', '.join(missing)}", file=sys.stderr)
        print(f"        {hint}", file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", default=None, help="待分析目录；留空则读 config.yaml 的 target_dir")
    ap.add_argument("--out", default=None, help="输出目录，默认读 config.yaml 的 output_dir")
    ap.add_argument("--config", default=None, help="配置文件，默认仓库根目录的 config.yaml")
    ap.add_argument("--disciplines", default=None, help="学科清单，默认读 config.yaml 的 disciplines_yaml")
    ap.add_argument("--template", default=None, help="HTML 模板，默认读 config.yaml 的 html_template")
    ap.add_argument("--knowledge-source", default=None, choices=["network", "local", "builtin"])
    ap.add_argument("--local-dir", default=None,
                    help="本地知识库目录，默认读 config.yaml 的 local_knowledge_dir")
    ap.add_argument("--html", default=None,
                    help="HTML 输出路径；留空则读 config.yaml 的 output_html，再回退到 --out/report.html")
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

    root = Path(__file__).resolve().parent
    config_path = (Path(args.config).expanduser().resolve()
                   if args.config else root / "config.yaml")
    cfg = load_config(config_path)

    target_value = args.target_dir or cfg.get("target_dir")
    if not target_value:
        print("[error] 未提供 --target-dir，config.yaml 的 target_dir 也为空", file=sys.stderr)
        sys.exit(1)
    target_dir = Path(target_value).expanduser().resolve()
    if not target_dir.exists():
        print(f"[error] 目标目录不存在: {target_dir}", file=sys.stderr)
        sys.exit(1)
    out = (Path(args.out).expanduser().resolve()
           if args.out else resolve_project_path(root, cfg.get("output_dir") or "./output"))
    disciplines = (Path(args.disciplines).expanduser().resolve()
                   if args.disciplines else resolve_project_path(
                       root, cfg.get("disciplines_yaml") or "./knowledge/disciplines.yaml"))
    template = (Path(args.template).expanduser().resolve()
                if args.template else resolve_project_path(
                    root, cfg.get("html_template") or "./templates/report.html.j2"))
    local_dir = (Path(args.local_dir).expanduser().resolve()
                 if args.local_dir else resolve_project_path(
                     root, cfg.get("local_knowledge_dir") or "./knowledge/references"))
    knowledge_source = args.knowledge_source or cfg.get("knowledge_source") or "builtin"
    if knowledge_source not in ("network", "local", "builtin"):
        print(f"[error] knowledge_source 取值无效: {knowledge_source}", file=sys.stderr)
        sys.exit(1)
    if args.html:
        html_path = Path(args.html).expanduser().resolve()
    elif args.out:
        # 显式给了 --out 时，HTML 跟着输出目录走，不被 config 的 output_html 拉到别处
        html_path = out / "report.html"
    elif cfg.get("output_html"):
        html_path = resolve_project_path(root, cfg["output_html"])
    else:
        html_path = out / "report.html"
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "files_manifest.json"

    if args.force and not args.run_llm_check:
        print("[warn] --force 只影响渲染阶段，本次没有 --run-llm-check，该参数不会生效",
              file=sys.stderr)

    if args.skip_scripts:
        print("[run] 已跳过全部脚本步骤（--skip-scripts），沿用已有产物。")
    else:
        # 阶段1：三份产物都只读原文，不涉及任何 LLM 判定
        if args.skip_stage1:
            print("[run] 跳过阶段1（--skip-stage1），沿用 ingest/stats/timeline 产物。")
            require_files(
                [manifest, out / "stats.json", out / "keywords.json", out / "timeline.json"],
                "请先跑不带 --skip-stage1 的完整阶段1，或补齐上述文件。")
        else:
            run([sys.executable, str(SCRIPTS_DIR / "ingest.py"),
                 "--target-dir", target_dir, "--out", out, "--config", config_path])

            run([sys.executable, str(SCRIPTS_DIR / "stats.py"),
                 "--manifest", manifest, "--out", out, "--config", config_path])

            run([sys.executable, str(SCRIPTS_DIR / "timeline.py"),
                 "--manifest", manifest, "--out", out])

        # 阶段2：标记层只能由 LLM 通读原文产出，脚本替代不了
        annotation_path = out / "annotation.json"
        if not annotation_path.exists():
            print("\n[待办] 标记层 annotation.json 缺失。")
            print("       请 LLM 通读原文，按 prompts/annotate.md 产出标记层：")
            print("       - quotes[]：判定「什么算引用」（含来源/功能/依据）")
            print("       - discipline_plan：判定学科路由（core/secondary/excluded + 依据）")
            print(f"       写入 {annotation_path} 后重跑：")
            print(f"      python run.py --target-dir {target_dir} --skip-stage1")
            sys.exit(2)

        # 阶段3：以下脚本都要读标记层产物，缺 annotation 就跑不动
        require_files(
            [out / "stats.json", out / "keywords.json", out / "timeline.json"],
            "阶段3需要阶段1的统计产物，请先补齐再重跑。")

        run([sys.executable, str(SCRIPTS_DIR / "quotes.py"),
             "--manifest", manifest, "--out", out, "--config", config_path,
             "--annotation", annotation_path])

        run([sys.executable, str(SCRIPTS_DIR / "discipline_router.py"),
             "--manifest", manifest,
             "--stats", out / "stats.json",
             "--keywords", out / "keywords.json",
             "--quotes", out / "quotes.json",
             "--timeline", out / "timeline.json",
             "--disciplines", disciplines, "--out", out,
             "--annotation", annotation_path])

        concepts = gen_concepts_json(disciplines, out)
        run([sys.executable, str(SCRIPTS_DIR / "knowledge_lookup.py"),
             "--concepts", concepts,
             "--source", knowledge_source,
             "--local-dir", local_dir, "--out", out])

        emotion_annotation = out / "emotion_annotation.json"
        if emotion_annotation.exists():
            run([sys.executable, str(SCRIPTS_DIR / "emotion_dynamics.py"),
                 "--annotation", emotion_annotation, "--out", out])
        else:
            print("[info] 未找到 emotion_annotation.json，跳过 UED 情感指标。")

    # 分析产物缺失时先摆出待办并退出，补齐后再从断点接着跑
    missing = [j for j in LLM_JSON if not (out / j).exists()]
    if missing:
        print("\n[待办] 以下分析 JSON 需由 LLM 按 SKILL.md 分批生成：")
        for j in missing:
            print(f"  - {j}")
        print("提示：单篇 Map 每批 3-5 篇（见 config.yaml chunk_batch），")
        print("      逐学科分析按 discipline_plan.json 的 core 学科逐个产出。")
        print("      生成后重新运行：")
        print(f"      python run.py --target-dir {target_dir} --run-llm-check --skip-scripts")
        sys.exit(2)

    # 产物齐全才渲染，免得交付一份只有统计表的报告
    if args.run_llm_check:
        # 渲染前先拦内容，免得一份不合格的报告被当成成品发出去
        gate_rc = run_gate(out, config_path)
        if gate_rc != 0 and not args.force:
            print("\n[闸门] validate.py 检测到 fail，已拒绝渲染 HTML。")
            print("       请按上方 [FAIL] 清单修复（补齐深度 / 核验文献 / 修隐私等）后重跑；")
            print("       或追加 --force 强制生成「不合格草稿」。")
            sys.exit(1)
        build_cmd = [sys.executable, str(SCRIPTS_DIR / "build_html.py"),
                     "--data-dir", out, "--out", html_path, "--template", template]
        if args.force:
            build_cmd.append("--force")
        run(build_cmd)
        if run_post_check(out, config_path, html_path) != 0:
            print("\n[闸门] 渲染后校验未通过，详见上方输出。", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n[完成] 脚本统计步骤已全部完成；LLM 分析 JSON 已齐，")
        print("       如需生成 HTML，追加 --run-llm-check --skip-scripts 重跑（不重算脚本）。")


if __name__ == "__main__":
    main()
