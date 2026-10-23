import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


QUOTE_PATTERNS = [
    ("cn_quote", re.compile(r"“([^”]{6,200})”")),
    ("en_quote", re.compile(r'"([^"]{6,200})"')),
    ("book_title", re.compile(r"《([^》]{1,100})》")),
    ("piece_title", re.compile(r"〈([^〉]{1,100})〉")),
]

DEFAULT_CITATION_VERBS = [
    "说", "写道", "提到", "引用", "如", "所谓", "记得",
    "有人说", "书上说", "曾言", "尝云",
]

# 来源猜测关键词：只看引号前 50 字上下文，顺序即优先级
SOURCE_KEYWORDS = {
    "自引": ["我说", "我写", "我命名", "我称之为", "我所谓", "我总结", "我写下"],
    "他人": ["他说", "她说", "有人说", "写道", "记载", "曰"],
    "书": ["书", "小说", "著作", "读", "书中", "原文"],
    "文章": ["文章", "论文", "报道", "白皮书", "文中"],
    "歌词": ["歌", "歌词", "唱", "旋律"],
    "电影": ["电影", "影片", "镜头", "台词", "剧"],
}

# 完整主谓结构的轻量判定：句内/句末标点，或常见谓词/系词
CLAUSE_PUNCT = "，。！？；：、……—"
PREDICATE_HINTS = (
    "是", "有", "在", "说", "认为", "觉得", "需要", "成为", "进行",
    "没有", "会", "要", "能", "想", "知道", "应该", "可以", "把", "被",
    "让", "对", "与", "和", "或", "而", "但", "却", "了", "着", "过",
)


def load_config(cfg_path):
    cfg = {
        "quote_patterns": [],
        "citation_verbs": DEFAULT_CITATION_VERBS,
    }
    if cfg_path and Path(cfg_path).exists() and yaml is not None:
        with open(cfg_path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        cfg.update({k: v for k, v in user.items() if k in cfg})
    return cfg


def has_subject_predicate(text: str) -> bool:
    """用标点与常见谓词判断引号里是不是一句话。

    做真正的句法分析代价太大，这里只需要把「引述」和「强调」分开。
    """
    if any(ch in text for ch in CLAUSE_PUNCT):
        return True
    return any(h in text for h in PREDICATE_HINTS)


def guess_source(context: str) -> str:
    """只看引号前的 50 字：引用自身几乎不会交代出处。"""
    for src, kws in SOURCE_KEYWORDS.items():
        if any(k in context for k in kws):
            return src
    return "不明"


def classify_quote(label, qtext, context_20, verbs):
    if label in ("book_title", "piece_title"):
        return True, "书名/篇名包裹"
    if any(v in context_20 for v in verbs):
        return True, "引述动词"
    if len(qtext) >= 15 and has_subject_predicate(qtext):
        return True, "完整主谓结构"
    return False, "强调/专名"


def _normalize(s: str) -> str:
    """去掉标点与空白：标记层抄回的文本常在标点上和原文有出入。"""
    return re.sub(r"[\s“”‘’\"'，。！？；：、…—\-（）()《》〈〉]", "", s)


def find_position(content: str, quote_text: str) -> str:
    """定位引用所在段落，逐级放宽比较方式。

    跨段引用只能按位置比例给近似段落号，读者仍能凭段落号找到大致位置。
    """
    # 精确匹配，段落号绝对准确
    idx = content.find(quote_text)
    if idx != -1:
        return f"第{content[:idx].count(chr(10)) + 1}段"
    norm_text = _normalize(quote_text)
    if not norm_text:
        return "位置未定位"
    # 逐段比对，容忍标点差异，段落号仍然准确
    for i, para in enumerate(content.split("\n"), start=1):
        if norm_text in _normalize(para):
            return f"第{i}段"
    # 全文比对，跨段引用只能按位置比例估算
    norm_content = _normalize(content)
    idx2 = norm_content.find(norm_text)
    if idx2 != -1:
        ratio = idx2 / len(norm_content)
        approx = int(ratio * len(content))
        return f"第{content[:approx].count(chr(10)) + 1}段"
    return "位置未定位"


def extract_quotes(item, cfg):
    content = item.get("content", "")
    name = item.get("name", "")
    quotes = []
    emphasis = []
    seen = set()  # 同一条引文会被多个模式同时命中，按 (type, text) 只留一次
    patterns = list(QUOTE_PATTERNS)
    for pat_str in cfg.get("quote_patterns", []):
        if isinstance(pat_str, str):
            try:
                patterns.append((pat_str, re.compile(pat_str)))
            except re.error:
                continue

    verbs = cfg.get("citation_verbs", DEFAULT_CITATION_VERBS)

    for label, pat in patterns:
        for m in pat.finditer(content):
            qtext = m.group(1).strip()
            if not qtext:
                continue
            # 引号里只剩两三个字的，多是强调词；书名与篇名不受这条限制
            if label in ("cn_quote", "en_quote") and len(qtext) < 6:
                continue
            context_20 = content[max(0, m.start() - 20):m.start()]
            context_50 = content[max(0, m.start() - 50):m.start()]
            is_quote, reason = classify_quote(label, qtext, context_20, verbs)
            entry = {
                "type": label,
                "text": qtext,
                "file": name,
                "position": find_position(content, qtext),
                "char_offset": m.start(),
                "source_guess": guess_source(context_50),
                "judgement": reason,
            }
            if is_quote:
                key = (label, qtext)
                if key in seen:
                    continue
                seen.add(key)
                quotes.append(entry)
            else:
                emphasis.append(entry)

    verb_hits = []
    sentences = re.split(r"[。！？!?\n]", content)
    for s in sentences:
        for v in verbs:
            if v in s:
                verb_hits.append({"verb": v, "sentence": s.strip()[:80]})
                break

    return quotes, emphasis, verb_hits


def annotate_from_markup(manifest, annotation):
    """标记层只给出引用文本，段落号与字符偏移必须回到原文里现算。"""
    content_by_name = {}
    for item in manifest["files"]:
        content = item.get("content", "")
        content_by_name[item.get("name")] = content
        # 标记层可能写文件名，也可能写路径，两种写法都要能对上
        p = item.get("file", "")
        if p:
            content_by_name[Path(p).name] = content

    all_quotes = []
    all_emphasis = []
    per_file_map = {}
    seen = set()

    for q in annotation.get("quotes", []):
        name = q.get("file", "")
        text = q.get("text", "")
        if not text:
            continue
        content = content_by_name.get(name, "")
        key = (name, text)
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "type": "llm_marked",
            "text": text,
            "file": name,
            "position": find_position(content, text) if content else "位置未定位",
            "char_offset": content.find(text) if content else -1,
            "source_guess": q.get("source_guess", "不明"),
            "judgement": q.get("judgement", "LLM 标记"),
            "function": q.get("function", ""),
            "interpretation": q.get("interpretation", ""),
        }
        all_quotes.append(entry)
        per_file_map.setdefault(name, {"quotes": [], "emphasis": []})
        per_file_map[name]["quotes"].append(entry)

    for e in annotation.get("emphasis_quotes", []):
        name = e.get("file", "")
        text = e.get("text", "")
        if not text:
            continue
        content = content_by_name.get(name, "")
        entry = {
            "type": "emphasis",
            "text": text,
            "file": name,
            "position": find_position(content, text) if content else "位置未定位",
            "source_guess": "强调/专名",
            "judgement": "强调/专名（不计入引用）",
        }
        all_emphasis.append(entry)
        per_file_map.setdefault(name, {"quotes": [], "emphasis": []})
        per_file_map[name]["emphasis"].append(entry)

    # 按 manifest 顺序输出，报告的章节顺序与原文顺序一致
    per_file = []
    total_chars = 0
    for item in manifest["files"]:
        name = item.get("name")
        content = item.get("content", "")
        total_chars += len(re.sub(r"\s+", "", content))
        pf = per_file_map.get(name, {"quotes": [], "emphasis": []})
        per_file.append({
            "file": name,
            "path": item.get("file"),
            "quote_count": len(pf["quotes"]),
            "emphasis_count": len(pf["emphasis"]),
            "quotes": pf["quotes"],
            "emphasis_quotes": pf["emphasis"],
            "citation_verbs": [],
        })

    return all_quotes, all_emphasis, per_file, total_chars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default="./output")
    ap.add_argument("--config", default="./config.yaml")
    ap.add_argument("--annotation", default="",
                    help="标记层 annotation.json；提供则走「LLM 判定 + 脚本定位」路径，"
                         "否则走旧启发式（legacy，脚本自行判定）")
    args = ap.parse_args()

    cfg = load_config(args.config)

    with open(args.manifest, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    annotation = None
    if args.annotation and Path(args.annotation).exists():
        with open(args.annotation, "r", encoding="utf-8-sig") as f:
            annotation = json.load(f)

    all_quotes = []
    all_emphasis = []
    per_file = []
    total_chars = 0
    method = {}

    if annotation is not None:
        all_quotes, all_emphasis, per_file, total_chars = annotate_from_markup(manifest, annotation)
        method = {
            "judgement": "LLM 标记层判定（annotation.json）+ 脚本精确定位与计数",
            "source": "annotation.json",
        }
    else:
        # 没有 annotation 只能退回启发式，判定规则与标记层不同，误判会多一些
        for item in manifest["files"]:
            content = item.get("content", "")
            total_chars += len(re.sub(r"\s+", "", content))
            quotes, emphasis, verb_hits = extract_quotes(item, cfg)
            per_file.append({
                "file": item.get("name"),
                "path": item.get("file"),
                "quote_count": len(quotes),
                "emphasis_count": len(emphasis),
                "quotes": quotes,
                "emphasis_quotes": emphasis,
                "citation_verbs": verb_hits,
            })
            all_quotes.extend(quotes)
            all_emphasis.extend(emphasis)
        method = {
            "quote_min_len": 6,
            "quote_max_len": 200,
            "judgement": (
                "【legacy 启发式，建议改用 annotation.json 标记层】三者满足其一计入引用："
                "①引述动词在引号前 20 字内；②书名号/篇名号包裹；"
                "③引号内容 ≥ 15 字且含完整主谓结构。其余引号内容归入 emphasis_quotes，"
                "不计入引用总数。source_guess 仅依据引号前 50 字上下文。"
            ),
            "citation_verbs": DEFAULT_CITATION_VERBS,
        }

    source_dist = {}
    for q in all_quotes:
        s = q["source_guess"]
        source_dist[s] = source_dist.get(s, 0) + 1

    result = {
        "per_file": per_file,
        "total_quotes": len(all_quotes),
        "total_emphasis_quotes": len(all_emphasis),
        "quote_chars": sum(len(q["text"]) for q in all_quotes),
        "total_chars": total_chars,
        "density": round(sum(len(q["text"]) for q in all_quotes) / total_chars, 6) if total_chars else 0,
        "source_distribution": source_dist,
        "quotes": all_quotes,
        "emphasis_quotes": all_emphasis,
        "method": method,
    }

    out_path = out_dir / "quotes.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] 抽取 {len(all_quotes)} 条引用（{len(all_emphasis)} 条强调引号）-> {out_path}")
    print(json.dumps({"total_quotes": len(all_quotes),
                      "total_emphasis_quotes": len(all_emphasis),
                      "density": result["density"],
                      "source_distribution": source_dist}, ensure_ascii=False))


if __name__ == "__main__":
    main()
