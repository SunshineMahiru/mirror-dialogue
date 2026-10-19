#!/usr/bin/env python3
"""
timeline.py — 日期识别、时间线、情感曲线

功能：
- 识别文本中的日期（YYYY-MM-DD / YYYY年M月D日 / MM-DD / M月D日 / 相对时间词）
- 按日期/篇序构建时间线
- 基于情绪词典计算每篇情感得分，形成情感曲线
- 写作时间倾向（清晨/深夜）、季节

输出：timeline.json

用法：
    python timeline.py --manifest <files_manifest.json> [--out <输出目录>] [--config <config.yaml>]
"""

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
    (re.compile(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?"), "full"),
    (re.compile(r"(\d{4})[-/年](\d{1,2})月?"), "year_month"),
    (re.compile(r"(\d{1,2})月(\d{1,2})日"), "month_day"),
    (re.compile(r"(\d{1,2})[-/](\d{1,2})"), "month_day_num"),
]

# 情绪词典（正向/负向），可扩展
POSITIVE_WORDS = {
    "快乐", "高兴", "喜悦", "幸福", "平静", "安心", "感恩", "感激", "希望",
    "满足", "温暖", "轻松", "喜欢", "爱", "美好", "明亮", "欣慰", "治愈",
}
NEGATIVE_WORDS = {
    "悲伤", "难过", "痛苦", "焦虑", "愤怒", "孤独", "寂寞", "恐惧", "羞耻",
    "疲惫", "疲惫不堪", "绝望", "无助", "压抑", "失落", "沮丧", "愧疚", "自责",
}
# 情绪强度修饰（否定与程度）
NEGATION = {"不", "没", "无", "没有"}
AMPLIFIER = {"很", "非常", "极其", "特别", "太", "十分", "格外"}
DIMINISHER = {"有点", "稍微", "略", "些微", "一点点"}

TIME_SLOTS = {
    "清晨": ["清晨", "凌晨", "早上", "早晨", "日出"],
    "上午": ["上午"],
    "下午": ["下午", "午后"],
    "傍晚": ["傍晚", "黄昏"],
    "深夜": ["深夜", "凌晨", "半夜", "夜里", "夜晚", "夜深"],
}
SEASONS = {
    "春": ["春", "三月", "四月", "五月"],
    "夏": ["夏", "六月", "七月", "八月", "炎热"],
    "秋": ["秋", "九月", "十月", "十一月"],
    "冬": ["冬", "十二月", "一月", "二月", "寒冷", "雪"],
}


def extract_date(text):
    for pat, kind in DATE_PATTERNS:
        m = pat.search(text)
        if m:
            if kind == "full":
                y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
                return f"{y}-{mo:02d}-{d:02d}"
            if kind == "year_month":
                return f"{m.group(1)}-{int(m.group(2)):02d}"
            if kind in ("month_day", "month_day_num"):
                return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def sentiment_score(text):
    """简单词典法情感得分，范围约 [-1, 1]。"""
    score = 0.0
    hits = 0
    for w in POSITIVE_WORDS:
        score += text.count(w)
        hits += text.count(w)
    for w in NEGATIVE_WORDS:
        score -= text.count(w)
        hits += text.count(w)
    if hits == 0:
        return 0.0, "中性", []
    normalized = max(-1.0, min(1.0, score / hits))
    if normalized > 0.15:
        label = "偏正向"
    elif normalized < -0.15:
        label = "偏负向"
    else:
        label = "中性"
    return round(normalized, 3), label, []


def detect_time_slot(text):
    for slot, kws in TIME_SLOTS.items():
        for kw in kws:
            if kw in text:
                return slot
    return ""


def detect_season(text):
    seasons = []
    for s, kws in SEASONS.items():
        for kw in kws:
            if kw in text:
                seasons.append(s)
                break
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
        # 优先使用 frontmatter 中的日期字段，其次从正文提取
        date = item.get("date") or extract_date(text)
        score, label, _ = sentiment_score(text)
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

    # 时间范围
    dated = [e for e in entries if e["date_guess"]]
    date_range = [min(e["date_guess"] for e in dated), max(e["date_guess"] for e in dated)] if dated else []

    # 时间槽分布
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
        # 方法说明：情感曲线为规则词典法，非模型推断，报告须如实标注
        "method": {
            "sentiment": "规则词典法（内置正负情绪词典 + 频率归一化到 [-1,1]）",
            "limitation": "词典规模有限，不区分反讽/否定语境，仅作粗粒度情感倾向，"
                          "不能替代 LLM 逐句情感解读",
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
