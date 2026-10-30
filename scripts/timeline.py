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


DATE_PATTERNS = [
    (re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?"), "full"),
    (re.compile(r"(\d{4})[-/.年](\d{1,2})月?"), "year_month"),
    (re.compile(r"(\d{1,2})月(\d{1,2})日"), "month_day"),
    (re.compile(r"(\d{1,2})[-/](\d{1,2})"), "month_day_num"),
]

# 情绪词典只收含义明确的正负词，含糊的词放进来会把曲线拉平
POSITIVE_WORDS = {
    "快乐", "高兴", "喜悦", "幸福", "平静", "安心", "感恩", "感激", "希望",
    "满足", "温暖", "轻松", "喜欢", "爱", "美好", "明亮", "欣慰", "治愈",
}
NEGATIVE_WORDS = {
    "悲伤", "难过", "痛苦", "焦虑", "愤怒", "孤独", "寂寞", "恐惧", "羞耻",
    "疲惫", "疲惫不堪", "绝望", "无助", "压抑", "失落", "沮丧", "愧疚", "自责",
}
NEGATION = {"不", "没", "无", "没有"}
AMPLIFIER = {"很", "非常", "极其", "特别", "太", "十分", "格外"}
DIMINISHER = {"有点", "稍微", "略", "些微", "一点点"}

# 长词优先，避免「疲惫不堪」再被「疲惫」重复计一次
POSITIVE_RE = re.compile(
    "|".join(sorted(map(re.escape, POSITIVE_WORDS), key=len, reverse=True))
)
NEGATIVE_RE = re.compile(
    "|".join(sorted(map(re.escape, NEGATIVE_WORDS), key=len, reverse=True))
)

TIME_SLOTS = {
    "清晨": ["清晨", "早上", "早晨", "日出"],
    "上午": ["上午"],
    "下午": ["下午", "午后"],
    "傍晚": ["傍晚", "黄昏"],
    "深夜": ["深夜", "凌晨", "半夜", "夜里", "夜晚", "夜深"],
}
# 只用多字词，避免「青春」「夏令营」被当成季节
SEASONS = {
    "春": ["春天", "春季", "春日", "初春", "暮春", "三月", "四月", "五月"],
    "夏": ["夏天", "夏季", "夏日", "初夏", "盛夏", "六月", "七月", "八月", "炎热"],
    "秋": ["秋天", "秋季", "秋日", "初秋", "深秋", "九月", "十月", "十一月"],
    "冬": ["冬天", "冬季", "冬日", "初冬", "寒冬", "十二月", "一月", "二月",
           "寒冷", "下雪", "大雪", "雪花", "积雪"],
}
# 长词优先，避免「十一月」再被「一月」算成冬季
SEASON_KEYWORD_TO_SEASON = {kw: name for name, kws in SEASONS.items() for kw in kws}
SEASON_RE = re.compile(
    "|".join(sorted(map(re.escape, SEASON_KEYWORD_TO_SEASON), key=len, reverse=True))
)


def normalize_date(value: str) -> str:
    """把 frontmatter 里的日期压成 YYYY-MM 或 YYYY-MM-DD；无法解析时返回空串。"""
    m = re.match(r"^\s*(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2}))?", str(value))
    if not m:
        return ""
    month = int(m.group(2))
    day = int(m.group(3)) if m.group(3) else None
    if not 1 <= month <= 12:
        return ""
    if day is not None and not 1 <= day <= 31:
        return ""
    return f"{m.group(1)}-{month:02d}" + (f"-{day:02d}" if day else "")


def date_sort_key(value: str):
    try:
        nums = [int(p) for p in value.split("-")]
    except ValueError:
        return (9999, 12, 31)
    if len(nums) == 3:
        return tuple(nums)
    if len(nums) == 2:
        return (nums[0], nums[1], 0)
    return (9999, 12, 31)


def extract_date(text):
    """取正文里出现最早的那个日期；模式优先级只用于同一位置的取舍。"""
    best = None
    for pat, kind in DATE_PATTERNS:
        m = pat.search(text)
        if m and (best is None or m.start() < best[0].start()):
            best = (m, kind)
    if best is None:
        return ""
    m, kind = best
    if kind == "full":
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}-{mo:02d}-{d:02d}"
    if kind == "year_month":
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    if kind in ("month_day", "month_day_num"):
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _sentiment_hits(text, pattern, polarity):
    score = 0.0
    hits = 0
    for m in pattern.finditer(text):
        # 否定词只回看 4 个字，避免把上一句的否定带到本句
        ctx = text[max(0, m.start() - 4):m.start()]
        factor = 1.0
        if any(n in ctx for n in NEGATION):
            factor = -1.0
        elif any(a in ctx for a in AMPLIFIER):
            factor = 1.5
        elif any(d in ctx for d in DIMINISHER):
            factor = 0.7
        score += polarity * factor
        hits += 1
    return score, hits


def sentiment_score(text):
    pos_score, pos_hits = _sentiment_hits(text, POSITIVE_RE, 1.0)
    neg_score, neg_hits = _sentiment_hits(text, NEGATIVE_RE, -1.0)
    hits = pos_hits + neg_hits
    if hits == 0:
        return 0.0, "中性"
    normalized = max(-1.0, min(1.0, (pos_score + neg_score) / hits))
    if normalized > 0.15:
        label = "偏正向"
    elif normalized < -0.15:
        label = "偏负向"
    else:
        label = "中性"
    return round(normalized, 3), label


def detect_time_slot(text):
    for slot, kws in TIME_SLOTS.items():
        for kw in kws:
            if kw in text:
                return slot
    return ""


def detect_season(text):
    seasons = []
    for m in SEASON_RE.finditer(text):
        name = SEASON_KEYWORD_TO_SEASON[m.group(0)]
        if name not in seasons:
            seasons.append(name)
    return seasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default="./output")
    args = ap.parse_args()

    with open(args.manifest, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for idx, item in enumerate(manifest["files"]):
        text = item.get("content", "")
        # frontmatter 里的日期是作者自己写的，比正文里随手提到的日期可靠
        date = normalize_date(item.get("date")) or extract_date(text)
        score, label = sentiment_score(text)
        entries.append({
            "file": item.get("name"),
            "path": item.get("file"),
            "index": idx,
            "date_guess": date,
            "time_slot": detect_time_slot(text),
            "seasons": detect_season(text),
            "sentiment_score": score,
            "sentiment_label": label,
        })

    dated = [e for e in entries if e["date_guess"]]
    # 只有带年份的日期参与范围比较；月日与年月混排时字符串比较会颠倒
    year_dated = [e for e in dated if re.match(r"^\d{4}-", e["date_guess"])]
    year_dated.sort(key=lambda e: date_sort_key(e["date_guess"]))
    date_range = ([year_dated[0]["date_guess"], year_dated[-1]["date_guess"]]
                  if year_dated else [])

    slot_dist = Counter(e["time_slot"] for e in entries if e["time_slot"])
    season_dist = Counter(s for e in entries for s in e["seasons"])

    result = {
        "entries": entries,
        "date_range": date_range,
        "dated_count": len(dated),
        "time_slot_distribution": dict(slot_dist),
        "season_distribution": dict(season_dist),
        "sentiment_curve": [{"file": e["file"], "score": e["sentiment_score"],
                             "label": e["sentiment_label"]} for e in entries],
        # 词典法靠词频加减，读不出反讽与否定语境，下游引用这组数字时必须知道它的边界
        "method": {
            "sentiment": "规则词典法（内置正负情绪词典 + 频率归一化到 [-1,1]）",
            "limitation": "词典规模有限，否定只按前置否定词初步判断，不区分反讽，"
                          "仅作情感倾向参考，不能替代 LLM 逐句情感解读",
            "date_detection": "正则匹配 + frontmatter date 字段优先",
        },
    }

    out_path = out_dir / "timeline.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] 时间线/情感曲线 -> {out_path}")
    print(json.dumps({"dated_count": len(dated),
                      "date_range": date_range,
                      "time_slots": dict(slot_dist)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
