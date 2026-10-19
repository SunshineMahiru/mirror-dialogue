#!/usr/bin/env python3
"""
knowledge_lookup.py — 学科知识检索与来源记录

功能：
- network 模式：提示联网检索（本脚本不直接联网，而是生成检索指令与来源模板，
  由主 agent 依据知识查找规范执行；来源必须记录作者/标题/年份/页码或 URL/访问日期）
- local 模式：在本地知识库目录做关键词检索（文件名/内容关键词）
- builtin 模式：使用模型内置知识，标记 "模型内部知识，未检索，需核验"
- 输出 knowledge_sources.json，记录每个概念的来源与核验状态

用法：
    python knowledge_lookup.py --concepts <concepts.json> \
        --source <network|local|builtin> [--local-dir <目录>] --out <输出目录>
"""

import argparse
import json
import sys
from pathlib import Path


def search_local(local_dir, concept):
    """在本地知识库目录按文件名/内容关键词检索。"""
    hits = []
    root = Path(local_dir)
    if not root.exists():
        return hits
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".md", ".txt", ".json", ".yaml", ".yml"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if concept in p.name or concept in text[:20000]:
            hits.append({"file": str(p), "matched": concept, "snippet": text[:300]})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concepts", required=True, help="concepts.json，含每学科概念列表")
    ap.add_argument("--source", default="builtin", choices=["network", "local", "builtin"])
    ap.add_argument("--local-dir", default="./knowledge/references")
    ap.add_argument("--out", default="./output")
    args = ap.parse_args()

    with open(args.concepts, "r", encoding="utf-8-sig") as f:
        concepts_data = json.load(f)

    records = []
    for discipline in concepts_data.get("disciplines", []):
        dname = discipline.get("name", discipline.get("id", ""))
        for c in discipline.get("concepts", []):
            concept = c if isinstance(c, str) else c.get("name", "")
            if not concept:
                continue
            rec = {
                "discipline": dname,
                "concept": concept,
                "mode": args.source,
                "source": "",
                "verified": False,
                "note": "",
            }
            if args.source == "local":
                hits = search_local(args.local_dir, concept)
                if hits:
                    rec["source"] = hits[0]["file"]
                    rec["verified"] = True
                    rec["note"] = "本地知识库命中"
                else:
                    rec["note"] = "本地知识库未命中，需人工补充或标'未检索，需核验'"
            elif args.source == "builtin":
                rec["note"] = "模型内部知识，未检索，需核验"
            else:  # network
                rec["note"] = "联网检索（由主 agent 执行并记录作者/标题/年份/页码或URL/访问日期）"
            records.append(rec)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "knowledge_sources.json"
    out_path.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"[ok] 知识来源记录 -> {out_path}")
    print(json.dumps({"mode": args.source, "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
