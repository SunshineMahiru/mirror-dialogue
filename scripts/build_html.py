import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def load_json(path):
    if path and Path(path).exists():
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"[error] {path} 无法解析为 JSON（第 {e.lineno} 行第 {e.colno} 列）: {e.msg}",
                  file=sys.stderr)
            sys.exit(1)
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
    errors = []
    if not ctx.get("stats"):
        errors.append("缺少 stats.json")
    if not ctx.get("quotes"):
        errors.append("缺少 quotes.json")
    qs = ctx.get("quotes")
    if qs:
        # 引用没有段落号，读者就回不到原文核对
        bad = [q for q in qs.get("quotes", []) if not q.get("position")]
        if bad:
            errors.append(f"{len(bad)} 条引用缺少位置标注")
    return errors


def load_gate_report(data_dir):
    """读闸门报告里的 fail 项。

    强制渲染时要把这些问题摆在页面顶部，读者才知道手里拿的是草稿。
    报告缺失或损坏时返回 None，页面据此标注「未运行」，不能写成「已通过」。
    """
    p = Path(data_dir) / "validation_report.json"
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warn] 无法读取 {p}: {e}", file=sys.stderr)
        return None


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

    # 有 fail 却仍然出图时，页面必须自己说明这是草稿
    gate = load_gate_report(args.data_dir)
    draft_failures = (gate or {}).get("fail", [])
    ctx["is_draft"] = args.force and bool(draft_failures)
    ctx["draft_failures"] = draft_failures if ctx["is_draft"] else []
    if ctx["is_draft"]:
        ctx["validation_status"] = "不合格草稿（--force 强制渲染）"
    elif gate is None:
        ctx["validation_status"] = "未运行事前闸门校验"
    elif draft_failures:
        ctx["validation_status"] = "未通过事前闸门校验"
    else:
        ctx["validation_status"] = "已通过事前闸门校验"

    html = render(Path(args.template), ctx, args.out)
    print(f"[ok] HTML 已生成 -> {args.out}（{len(html)} 字符）")


if __name__ == "__main__":
    main()
