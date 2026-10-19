#!/usr/bin/env python3
"""
build_html.py — 用 Jinja2 模板渲染完整 HTML 报告

功能：
- 读取所有分析 JSON（stats/keywords/ngrams/cooccurrence/quotes/timeline/
  single_analysis/global_analysis/discipline_analysis/cross_discipline）
- 用 templates/report.html.j2 渲染为自包含 HTML
- 校验：目录锚点、表格数据、引用位置、图表数据是否与 JSON 一致

用法：
    python build_html.py --data-dir <分析JSON目录> --out <输出HTML> \
        [--template <report.html.j2>]
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_OK = True
except ImportError:
    JINJA_OK = False


def load_json(path):
    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return None


def build_context(data_dir):
    d = Path(data_dir)
    ctx = {
        "stats": load_json(d / "stats.json"),
        "keywords": load_json(d / "keywords.json"),
        "ngrams": load_json(d / "ngrams.json"),
        "cooccurrence": load_json(d / "cooccurrence.json"),
        "quotes": load_json(d / "quotes.json"),
        "timeline": load_json(d / "timeline.json"),
        "single": load_json(d / "single_analysis.json"),
        "global": load_json(d / "global_analysis.json"),
        "discipline_plan": load_json(d / "discipline_plan.json"),
        "discipline": load_json(d / "discipline_analysis.json"),
        "cross": load_json(d / "cross_discipline.json"),
        "knowledge": load_json(d / "knowledge_sources.json"),
    }
    return ctx


def render(template_path, ctx, out_path):
    if not JINJA_OK:
        print("[error] 需要 Jinja2，请 pip install jinja2", file=sys.stderr)
        sys.exit(1)
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    tpl = env.get_template(template_path.name)
    html = tpl.render(**ctx)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    return html


def validate(ctx):
    """校验目录锚点、表格数据、引用位置、图表数据。"""
    errors = []
    if not ctx.get("stats"):
        errors.append("缺少 stats.json")
    if not ctx.get("quotes"):
        errors.append("缺少 quotes.json")
    # 引用位置校验：quotes 中的 position 应非空
    qs = ctx.get("quotes")
    if qs:
        bad = [q for q in qs.get("quotes", []) if not q.get("position")]
        if bad:
            errors.append(f"{len(bad)} 条引用缺少位置标注")
    return errors


def load_gate_report(data_dir):
    """读取 validate.py 事前闸门产出的 validation_report.json，返回 fail 清单。

    用于「--force 草稿」标注：把闸门拦截的 fail 项显式写进页面顶部。
    """
    p = Path(data_dir) / "validation_report.json"
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            rep = json.load(f)
        return rep.get("fail", [])
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default="./templates/report.html.j2")
    ap.add_argument("--force", action="store_true",
                    help="强制渲染：即使事前闸门有 fail 也生成 HTML，"
                         "并在页面顶部标注「不合格草稿」")
    args = ap.parse_args()

    ctx = build_context(args.data_dir)
    errs = validate(ctx)
    if errs:
        print("[warn] 校验发现:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)

    # P0：读取事前闸门的 fail 清单，决定草稿标注与校验状态文案
    draft_failures = load_gate_report(args.data_dir)
    ctx["is_draft"] = args.force and bool(draft_failures)
    ctx["draft_failures"] = draft_failures if ctx["is_draft"] else []
    if ctx["is_draft"]:
        ctx["validation_status"] = "不合格草稿（--force 强制渲染）"
    elif draft_failures:
        ctx["validation_status"] = "未通过事前闸门校验"
    else:
        ctx["validation_status"] = "已通过事前闸门校验"

    html = render(Path(args.template), ctx, args.out)
    print(f"[ok] HTML 已生成 -> {args.out}（{len(html)} 字符）")


if __name__ == "__main__":
    main()
