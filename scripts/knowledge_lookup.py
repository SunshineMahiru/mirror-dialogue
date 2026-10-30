import argparse
import json
from pathlib import Path

LOCAL_SUFFIXES = (".md", ".txt", ".json", ".yaml", ".yml")


def load_local_files(local_dir):
    """把本地知识库一次读进内存，避免每个概念都重扫一遍。"""
    root = Path(local_dir)
    if not root.exists():
        return []
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in LOCAL_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files.append((p, text))
    return files


def _relative_source(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def search_local(files, concept, local_dir):
    root = Path(local_dir)
    hits = []
    for p, text in files:
        idx = text.find(concept)
        if idx < 0 and concept not in p.name:
            continue
        # 片段围绕命中位置截取，读者能看到概念出现的上下文
        start = max(0, idx - 100) if idx >= 0 else 0
        hits.append({
            "file": _relative_source(p, root),
            "matched": concept,
            "snippet": text[start:start + 300],
        })
    return hits


def load_existing(out_path: Path):
    if not out_path.exists():
        return {}
    try:
        old = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {(r.get("discipline"), r.get("concept")): r for r in old.get("records", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concepts", required=True, help="concepts.json，含每学科概念列表")
    ap.add_argument("--source", default="builtin", choices=["network", "local", "builtin"])
    ap.add_argument("--local-dir", default="./knowledge/references")
    ap.add_argument("--out", default="./output")
    args = ap.parse_args()

    with open(args.concepts, "r", encoding="utf-8-sig") as f:
        concepts_data = json.load(f)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "knowledge_sources.json"
    existing = load_existing(out_path)
    local_files = load_local_files(args.local_dir) if args.source == "local" else []

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
                hits = search_local(local_files, concept, args.local_dir)
                if hits:
                    rec["source"] = hits[0]["file"]
                    rec["verified"] = True
                    rec["note"] = "本地知识库命中"
                else:
                    rec["note"] = "本地知识库未命中，需人工补充或标'未检索，需核验'"
            elif args.source == "builtin":
                rec["note"] = "模型内部知识，未检索，需核验"
            else:
                rec["note"] = "联网检索（由主 agent 执行并记录作者/标题/年份/页码或URL/访问日期）"

            # 人工补充过的核验状态与来源优先保留，重跑不覆盖
            old = existing.get((rec["discipline"], rec["concept"]))
            if old and (old.get("verified") or old.get("source")):
                rec["verified"] = bool(old.get("verified"))
                rec["source"] = old.get("source") or rec["source"]
                rec["note"] = old.get("note") or rec["note"]
            records.append(rec)

    out_path.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"[ok] 知识来源记录 -> {out_path}")
    print(json.dumps({"mode": args.source, "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
