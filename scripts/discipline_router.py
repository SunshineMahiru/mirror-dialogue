import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_disciplines(path):
    if yaml is None:
        print("[error] 需要 PyYAML 才能读取 disciplines.yaml", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("disciplines", [])


def feature_text(manifest, stats, keywords, quotes, timeline):
    """把可检索的文本拼在一起。

    正文必须算进去：没有 jieba 时关键词会退化成单字，命中不了多字触发词。
    """
    parts = []
    # 正文内容
    if manifest:
        for f in manifest.get("files", []):
            parts.append(f.get("content", ""))
    # 关键词词表 + TF-IDF
    if keywords:
        for kw in keywords.get("global", [])[:100]:
            parts.append(kw.get("word", ""))
        for kw in keywords.get("tfidf", [])[:50]:
            parts.append(kw.get("word", ""))
    # 引用文本
    if quotes:
        for q in quotes.get("quotes", [])[:200]:
            parts.append(q.get("text", ""))
    # 情感曲线标签、时间槽、季节
    if timeline:
        for e in timeline.get("entries", []):
            parts.append(e.get("sentiment_label", ""))
            parts.append(e.get("time_slot", ""))
            parts.extend(e.get("seasons", []))
    return " ".join(str(p) for p in parts if p)


def score_discipline(discipline, feat):
    when = discipline.get("when", "")
    kws = [k.strip() for k in re.split(r"[、，,]", when) if k.strip()]
    # concepts 与 evidence 只算半分，一个概念不该把学科顶进核心
    weak = []
    for key in ("concepts", "evidence"):
        for c in discipline.get(key, []):
            weak.append(c)
    score = 0
    hits = []
    for kw in kws:
        n = feat.count(kw)
        if n:
            score += n
            hits.append(kw)
    for w in weak:
        if w and w in feat:
            score += 0.5
            hits.append(w)
    return score, hits


def classify(scores):
    core, secondary, excluded = [], [], []
    total = sum(s for s in scores.values())
    avg = total / len(scores) if scores else 0
    for did, s in scores.items():
        if s >= max(avg * 1.2, 1.0):
            core.append(did)
        elif s > 0:
            secondary.append(did)
        else:
            excluded.append(did)
    return core, secondary, excluded


def evidence_hits_from_markup(manifest, disciplines):
    """数一数每个学科的触发词在正文里出现几次，给判定留个旁证。"""
    feat = feature_text(manifest, None, None, None, None)
    hit_map = {}
    for d in disciplines:
        did = d.get("id")
        when = d.get("when", "")
        kws = [k.strip() for k in re.split(r"[、，,]", when) if k.strip()]
        weak = []
        for key in ("concepts", "evidence"):
            for c in d.get(key, []):
                weak.append(c)
        hits = []
        for kw in kws:
            if kw and kw in feat:
                hits.append(kw)
        for w in weak:
            if w and w in feat:
                hits.append(w)
        seen = set()
        uniq = []
        for h in hits:
            if h not in seen:
                seen.add(h)
                uniq.append(h)
        hit_map[did] = uniq
    return hit_map


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="")
    ap.add_argument("--stats", default="")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--quotes", default="")
    ap.add_argument("--timeline", default="")
    ap.add_argument("--disciplines", required=True)
    ap.add_argument("--out", default="./output")
    ap.add_argument("--annotation", default="",
                    help="标记层 annotation.json；提供且含 discipline_plan 时，"
                         "路由判定交给 LLM、脚本只做证据命中计数；否则走旧启发式")
    args = ap.parse_args()

    disciplines = load_disciplines(args.disciplines)

    def load(p):
        if p and Path(p).exists():
            with open(p, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        return None

    manifest = load(args.manifest)
    stats = load(args.stats)
    keywords = load(args.keywords)
    quotes = load(args.quotes)
    timeline = load(args.timeline)

    annotation = None
    if args.annotation and Path(args.annotation).exists():
        annotation = load(args.annotation)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "discipline_plan.json"

    if annotation is not None and annotation.get("discipline_plan"):
        # 标记层给出的路由优先，命中计数只在它没写 evidence 时补位
        ap_plan = annotation["discipline_plan"]
        core = list(ap_plan.get("core_disciplines", []))
        secondary = list(ap_plan.get("secondary_disciplines", []))
        excluded = list(ap_plan.get("excluded_disciplines", []))
        reasons = dict(ap_plan.get("reasons", {}))
        llm_evidence = dict(ap_plan.get("evidence", {}))
        # 数字人文始终进入 core（作为统计基础）
        dids = {d.get("id") for d in disciplines}
        if "digital_humanities" in dids and "digital_humanities" not in core:
            core.append("digital_humanities")
            if "digital_humanities" in excluded:
                excluded.remove("digital_humanities")
            if "digital_humanities" in secondary:
                secondary.remove("digital_humanities")
        hit_map = evidence_hits_from_markup(manifest, disciplines)
        plan = {
            "core_disciplines": core,
            "secondary_disciplines": secondary,
            "excluded_disciplines": excluded,
            "scores": {},
            "evidence": {did: (llm_evidence.get(did) or hit_map.get(did) or []) for did in core},
            "hit_counts": {did: len(hit_map.get(did) or []) for did in core},
            "reasons": reasons,
            "method": "LLM 标记层判定路由 + 脚本证据命中计数",
        }
    else:
        # 没有标记层时按平均分划线，命中次数高的进核心，命中过的进次要
        feat = feature_text(manifest, stats, keywords, quotes, timeline)
        scores = {}
        hit_map = {}
        for d in disciplines:
            did = d.get("id")
            s, hits = score_discipline(d, feat)
            scores[did] = s
            hit_map[did] = hits
        core, secondary, excluded = classify(scores)
        if "digital_humanities" in scores and "digital_humanities" not in core:
            core.append("digital_humanities")
            if "digital_humanities" in excluded:
                excluded.remove("digital_humanities")
            if "digital_humanities" in secondary:
                secondary.remove("digital_humanities")
        plan = {
            "core_disciplines": core,
            "secondary_disciplines": secondary,
            "excluded_disciplines": excluded,
            "scores": scores,
            "evidence": {did: hit_map[did] for did in core},
            "reasons": {
                did: f"触发词命中: {', '.join(hit_map[did][:8]) or '无显式触发，作为统计/基础学科启用'}"
                for did in core
            },
            "method": "【legacy 启发式】关键词计数 + avg*1.2 一刀切（建议改用 annotation.json 标记层）",
        }

    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] 学科路由 -> {out_path}")
    print(json.dumps({
        "core": plan["core_disciplines"],
        "secondary": plan["secondary_disciplines"],
        "excluded": plan["excluded_disciplines"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
