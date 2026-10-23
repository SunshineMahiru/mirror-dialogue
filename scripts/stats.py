import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    import jieba
    JIEBA_OK = True
except ImportError:
    JIEBA_OK = False

try:
    import jieba.posseg as pseg
    POSSEG_OK = True
except ImportError:
    pseg = None
    POSSEG_OK = False


# 保留词性：名词、人名、地名、机构名、名动词、名形词、形容词
KEEP_POS = {"n", "nr", "ns", "nt", "vn", "an", "a"}

# 内置停用词；config.stopwords_file 里的词会追加进这份集合，改不到它的内容
BUILTIN_STOPWORDS = {
    # ---- 单字虚词 ----
    "的", "了", "是", "在", "有", "和", "与", "或", "也", "都", "就",
    "而", "但", "却", "又", "很", "个", "一", "之", "于", "及", "并",
    "被", "把", "让", "着", "到", "从", "对", "为", "以", "所", "等",
    "还", "要", "会", "能", "可", "没", "啊", "吧", "呢", "哦", "么",
    "得", "地", "过", "吗", "呀", "啦", "罢", "呗", "嘛", "喔", "嗯",
    "矣", "乎", "者", "其", "此", "彼", "何", "怎", "哪", "各", "每",
    "某", "咱", "俺", "尔", "汝", "这", "那", "不", "只", "才", "刚",
    "已", "将", "正", "再", "最", "更", "越", "太", "极",
    # ---- 代词 ----
    "我们", "你们", "他们", "她们", "它们", "自己", "自身", "本人",
    "大家", "别人", "他人", "这个", "那个", "这些", "那些", "这样",
    "那样", "这么", "那么", "怎么", "怎样", "什么", "多少", "这里",
    "那里", "哪里", "某个", "各位", "诸位", "彼此", "互相", "双方",
    "我方", "对方", "一个", "一些", "很多", "没有",
    # ---- 副词 ----
    "不是", "而是", "就是", "还是", "只是", "都是", "已经", "曾经",
    "正在", "将要", "即将", "尚未", "依然", "仍然", "忽然", "突然",
    "终于", "居然", "竟然", "果然", "当然", "必然", "显然", "其实",
    "确实", "的确", "似乎", "好像", "仿佛", "几乎", "简直", "偏偏",
    "反而", "反倒", "不断", "渐渐", "逐渐", "常常", "往往", "偶尔",
    "通常", "总是", "经常", "有时", "很少", "非常", "十分", "特别",
    "尤其", "极其", "格外", "更加", "最为", "不过", "大约", "大概",
    "也许", "或许", "可能", "可以", "应该", "应当", "必须", "需要",
    "值得", "能够", "得以", "只好", "只能", "只有", "只要", "不光",
    "不仅", "不但", "而且", "并且",
    # ---- 连词 ----
    "因为", "所以", "因此", "因而", "由于", "于是", "如果", "假如",
    "若是", "虽然", "尽管", "即使", "纵然", "但是", "可是", "然而",
    "否则", "不然", "然后", "接着", "随即", "随后", "从而", "进而",
    "以至", "以至于", "以及", "无论", "不论", "不管", "关于", "对于",
    "至于", "按照", "根据", "通过", "经过", "除了", "为了", "作为",
    # ---- 助词/方位/时间 ----
    "的话", "罢了", "而已", "为什么", "如何", "其中", "之间", "之中",
    "之内", "之外", "之前", "之后", "以前", "以后", "如今", "现在",
    "当下", "当时", "将来", "未来", "过去", "开始", "结束", "时候",
    "地方", "期间", "里面", "外面", "上面", "下面", "前面", "后面",
    "旁边", "周围",
    # ---- 虚化动词/情态/连接短语 ----
    "觉得", "认为", "知道", "发现", "感到", "感觉", "希望", "想要",
    "打算", "决定", "进行", "出现", "存在", "产生", "发生", "变成",
    "成为", "表示", "使得", "指出", "说明", "证明", "表达", "看起来",
    "可以说", "意味着", "相当于", "例如", "比如", "譬如", "诸如",
    "总之", "综上", "一是", "二是", "三是", "第一", "第二", "第三",
    "一方面", "另一方面", "其次", "再次", "最后", "首先", "此外",
    "另外",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ENWORD_RE = re.compile(r"[A-Za-z]+")
PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）《》〈〉,.!?;:'\"()\[\]{}<>…—\-…·\s]")
SENT_SPLIT_RE = re.compile(r"[。！？!?；;\n]")


def load_config(cfg_path):
    cfg = {
        "reading_speed_cpm": 300,
        "stopwords_file": "",
        "userdict_file": "",
        "tfidf_top_n": 50,
        "ngram_range": [2, 3],
        "cooccurrence_window": 8,
        "top_keywords_n": 30,
    }
    if cfg_path and Path(cfg_path).exists() and yaml is not None:
        with open(cfg_path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        # 只收已知键，配置里拼错的名字不会悄悄改掉默认值
        cfg.update({k: v for k, v in user.items() if k in cfg})
    return cfg


def load_stopwords(cfg):
    sw = set(BUILTIN_STOPWORDS)
    f = cfg.get("stopwords_file")
    if f and Path(f).exists():
        with open(f, "r", encoding="utf-8") as fh:
            sw.update(l.strip() for l in fh if l.strip())
    return sw


def load_userdict(cfg):
    f = cfg.get("userdict_file")
    if f and Path(f).exists() and JIEBA_OK:
        jieba.load_userdict(str(f))


def base_stats(text: str, cpm: int):
    raw = len(text)
    no_ws = len(re.sub(r"\s+", "", text))
    cjk = len(CJK_RE.findall(text))
    en_words = len(ENWORD_RE.findall(text))
    punct = len(PUNCT_RE.findall(text))
    paragraphs = len([p for p in text.split("\n") if p.strip()])
    sentences = [s.strip() for s in SENT_SPLIT_RE.split(text) if s.strip()]
    sentence_count = len(sentences)
    avg_sentence_len = round(cjk / sentence_count, 2) if sentence_count else 0.0
    reading_min = round(cjk / cpm, 2) if cpm else 0.0
    return {
        "raw_chars": raw,
        "chars_no_whitespace": no_ws,
        "chinese_chars": cjk,
        "english_words": en_words,
        "punctuation_count": punct,
        "paragraph_count": paragraphs,
        "sentence_count": sentence_count,
        "avg_sentence_len": avg_sentence_len,
        "reading_minutes": reading_min,
    }


def tokenize(text: str, sw: set):
    """不做词性过滤的切分，留给 n-gram、共现与纯词频使用。"""
    if JIEBA_OK:
        tokens = [w for w in jieba.cut(text) if w.strip()]
        return [w for w in tokens if w not in sw and len(w.strip()) > 1]
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z]+", text)
    return [w for w in tokens if w not in sw]


def tokenize_pos(text: str, sw: set):
    """只留名词与形容词，免得虚词挤满关键词表。"""
    if JIEBA_OK and POSSEG_OK:
        tokens = []
        for w, flag in pseg.cut(text):
            w = w.strip()
            if not w or w in sw:
                continue
            if flag not in KEEP_POS:
                continue
            if len(w) <= 1:
                continue
            tokens.append(w)
        return tokens
    # 没有 posseg 时词性过滤失效，只能退回按长度过滤
    if JIEBA_OK:
        tokens = [w for w in jieba.cut(text) if w.strip()]
        return [w for w in tokens if w not in sw and len(w.strip()) > 1]
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z]+", text)
    return [w for w in tokens if w not in sw and len(w.strip()) > 1]


def word_frequency(tokens):
    c = Counter(tokens)
    total = sum(c.values()) or 1
    return [{"word": w, "count": n, "ratio": round(n / total, 6)} for w, n in c.most_common()]


def attach_evidence(kw_list, sentences):
    for kw in kw_list:
        ev = ""
        for s in sentences:
            if kw["word"] in s:
                ev = s[:60]
                break
        kw["evidence"] = ev
    return kw_list


def tf_idf(docs, sw, top_n):
    """TF-IDF 手写一份，免得为一项统计拉进 sklearn。"""
    n_docs = len(docs)
    doc_tokens = [tokenize_pos(d, sw) for d in docs]
    df = defaultdict(int)
    for toks in doc_tokens:
        for w in set(toks):
            df[w] += 1
    scores = []
    for toks in doc_tokens:
        tf = Counter(toks)
        max_tf = max(tf.values()) if tf else 1
        doc_scores = {}
        for w, c in tf.items():
            idf = math.log((1 + n_docs) / (1 + df[w])) + 1
            doc_scores[w] = (c / max_tf) * idf
        scores.append(doc_scores)
    global_scores = Counter()
    for s in scores:
        for w, v in s.items():
            global_scores[w] += v
    top = [{"word": w, "score": round(v, 6)} for w, v in global_scores.most_common(top_n)]
    return top, df


def ngrams(tokens, n):
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def cooccurrence(texts, sw, window):
    pair_count = Counter()
    for text in texts:
        toks = tokenize(text, sw)
        for i in range(len(toks)):
            for j in range(i + 1, min(i + window + 1, len(toks))):
                a, b = toks[i], toks[j]
                if a != b:
                    pair_count[(min(a, b), max(a, b))] += 1
    return [{"pair": list(p), "count": c} for p, c in pair_count.most_common()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default="./output")
    ap.add_argument("--config", default="./config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sw = load_stopwords(cfg)
    load_userdict(cfg)
    cpm = cfg.get("reading_speed_cpm", 300)

    with open(args.manifest, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    stats_out = []
    keywords_out = []
    all_texts = []

    for item in manifest["files"]:
        text = item.get("content", "")
        st = base_stats(text, cpm)
        st["file"] = item.get("name")
        st["path"] = item.get("file")
        stats_out.append(st)

        sentences = [s.strip() for s in SENT_SPLIT_RE.split(text) if s.strip()]

        # 词频留两份：词性过滤后的进关键词，纯词频只作对照
        kws_pos = attach_evidence(word_frequency(tokenize_pos(text, sw)), sentences)
        kws_raw = attach_evidence(word_frequency(tokenize(text, sw)), sentences)

        keywords_out.append({
            "file": item.get("name"), "path": item.get("file"),
            "keywords": kws_pos[: cfg.get("top_keywords_n", 30)],
            "word_freq": kws_raw[: cfg.get("top_keywords_n", 30)],
        })
        all_texts.append(text)

    # 跨篇排序以 TF-IDF 为准：每篇都出现的词靠词频会被顶到前面，区分不了文章之间的差别
    tfidf_top, df_map = tf_idf(all_texts, sw, cfg.get("tfidf_top_n", 50))

    rng = cfg.get("ngram_range", [2, 3])
    ngram_out = {}
    if 2 in rng:
        bigram_c = Counter()
        for t in all_texts:
            bigram_c.update(ngrams(tokenize(t, sw), 2))
        ngram_out["bigram"] = [
            {"ngram": list(k), "count": v} for k, v in bigram_c.most_common(30)
        ]
    if 3 in rng:
        trigram_c = Counter()
        for t in all_texts:
            trigram_c.update(ngrams(tokenize(t, sw), 3))
        ngram_out["trigram"] = [
            {"ngram": list(k), "count": v} for k, v in trigram_c.most_common(30)
        ]

    cooc = cooccurrence(all_texts, sw, cfg.get("cooccurrence_window", 8))

    global_counter = Counter()
    global_pos_counter = Counter()
    for t in all_texts:
        global_counter.update(tokenize(t, sw))
        global_pos_counter.update(tokenize_pos(t, sw))

    global_sentences = [s.strip() for t in all_texts for s in SENT_SPLIT_RE.split(t) if s.strip()]

    total_tokens = sum(global_counter.values()) or 1
    total_pos_tokens = sum(global_pos_counter.values()) or 1
    global_kw = attach_evidence([
        {"word": w, "count": n, "ratio": round(n / total_tokens, 6)}
        for w, n in global_counter.most_common(cfg.get("top_keywords_n", 30))
    ], global_sentences)
    global_pos_kw = attach_evidence([
        {"word": w, "count": n, "ratio": round(n / total_pos_tokens, 6)}
        for w, n in global_pos_counter.most_common(cfg.get("top_keywords_n", 30))
    ], global_sentences)
    attach_evidence(tfidf_top, global_sentences)

    def dump(name, obj):
        p = out_dir / name
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    p1 = dump("stats.json", {"files": stats_out, "global": {
        "total_files": len(stats_out),
        "total_raw_chars": sum(s["raw_chars"] for s in stats_out),
        "total_chars_no_ws": sum(s["chars_no_whitespace"] for s in stats_out),
        "total_chinese_chars": sum(s["chinese_chars"] for s in stats_out),
        "total_english_words": sum(s["english_words"] for s in stats_out),
        "total_paragraphs": sum(s["paragraph_count"] for s in stats_out),
        "total_sentences": sum(s["sentence_count"] for s in stats_out),
        "method": {
            "tokenizer": "jieba" if JIEBA_OK else "char_fallback",
            "degraded": not JIEBA_OK,
            "degraded_note": ("未安装 jieba，词频/TF-IDF/n-gram/共现退化为按字切分，"
                              "多字词与词义统计精度下降") if not JIEBA_OK else "",
            "posseg": "jieba.posseg" if POSSEG_OK else "degraded（无 posseg，词性过滤失效）",
            "keep_pos": list(KEEP_POS),
            "stopword_count": len(sw),
        },
    }})
    p2 = dump("keywords.json", {
        "per_file": keywords_out,
        "global": global_kw,
        "global_pos_filtered": global_pos_kw,
        "tfidf": tfidf_top,
        "df": {w: n for w, n in df_map.items()},
        "pos_kept": list(KEEP_POS),
        "stopword_count": len(sw),
        "method": ("jieba.posseg 词性过滤（仅 n/nr/ns/nt/vn/an/a）+ 200+ 停用词 + 手写 TF-IDF"
                   if (JIEBA_OK and POSSEG_OK) else "按字切分降级（词性过滤失效）"),
        "note": ("global / per_file.word_freq 为纯词频表（含虚词，仅供参考）；"
                 "关键词以 tfidf（TF-IDF 排序）与 global_pos_filtered（词性过滤）为准。"),
    })
    p3 = dump("ngrams.json", ngram_out)
    p4 = dump("cooccurrence.json", {"pairs": cooc})

    print(f"[ok] stats.json / keywords.json / ngrams.json / cooccurrence.json -> {out_dir}")
    print(json.dumps({"files": len(stats_out),
                      "total_chars": sum(s["chinese_chars"] for s in stats_out),
                      "stopword_count": len(sw),
                      "posseg": POSSEG_OK}, ensure_ascii=False))


if __name__ == "__main__":
    main()
