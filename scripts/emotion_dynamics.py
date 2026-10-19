#!/usr/bin/env python3
"""
emotion_dynamics.py — UED 情感动力学指标计算（标记层路径）

读 LLM 标记层产出的 VAD 标注，计算每篇的 UED 动态指标。

职责边界（见 methodology/emotion-dynamics.md）：
- VAD 逐段标注 = LLM（标记层）做，见 prompts/annotate.md
- 指标计算 = 本脚本做（home base / variability / instability / density 等）

输入：emotion_annotation.json（LLM 产出）
输出：emotion_dynamics.json（每篇 6 项指标）

用法：
    python emotion_dynamics.py --annotation <emotion_annotation.json> --out <输出目录>
"""

import argparse
import json
import statistics
from pathlib import Path


def calc_metrics(segments):
    """从 VAD 标注序列计算 UED 指标。segments: [{valence, arousal, dominance, ...}]"""
    if not segments:
        return None
    vals = [s.get("valence", 0.0) for s in segments]
    arous = [s.get("arousal", 0.0) for s in segments]
    doms = [s.get("dominance", 0.5) for s in segments]

    # Home Base：均值
    home_base = {
        "valence": round(statistics.fmean(vals), 3),
        "arousal": round(statistics.fmean(arous), 3),
        "dominance": round(statistics.fmean(doms), 3),
    }

    # Variability：标准差（样本数 < 2 时为 0）
    def _std(xs):
        return round(statistics.pstdev(xs), 3) if len(xs) >= 2 else 0.0

    variability = {"valence": _std(vals), "arousal": _std(arous)}

    # Instability：相邻 |Δvalence| > 0.6 的跳变次数
    jumps = sum(1 for i in range(1, len(vals)) if abs(vals[i] - vals[i - 1]) > 0.6)
    instability = {"jumps": jumps, "level": _level(jumps, 0, 3)}

    # Density：明显情绪标注（|valence|>0.3 或 arousal>0.6）占比
    dense = sum(1 for v, a in zip(vals, arous) if abs(v) > 0.3 or a > 0.6)
    density = round(dense / len(segments), 3) if segments else 0.0

    # Rise / Recovery Rate：定性——找最大负→正跃迁与正→负回落
    rise_rate = _rise_rate(vals)
    recovery_rate = _recovery_rate(vals)

    # Inertia：定性——偏离基线后回归的段落数
    inertia = _inertia(vals, home_base["valence"])

    return {
        "home_base": home_base,
        "variability": variability,
        "instability": instability,
        "density": density,
        "rise_rate": rise_rate,
        "recovery_rate": recovery_rate,
        "inertia": inertia,
        "segment_count": len(segments),
    }


def _level(n, low_th, high_th):
    if n <= low_th:
        return "low"
    if n >= high_th:
        return "high"
    return "medium"


def _rise_rate(vals):
    """情感上升速率：统计相邻跃迁中负→正的最大斜率（定性）。"""
    rises = [vals[i] - vals[i - 1] for i in range(1, len(vals)) if vals[i] - vals[i - 1] > 0]
    if not rises:
        return {"level": "low", "comment": "无明显正向跃迁"}
    mx = max(rises)
    return {"level": _level(mx, 0.15, 0.45), "max_delta": round(mx, 3),
            "comment": "触发后情绪升高的快慢（越大越快）"}


def _recovery_rate(vals):
    """情感恢复速率：统计相邻跃迁中正→负的回落（定性）。"""
    drops = [vals[i - 1] - vals[i] for i in range(1, len(vals)) if vals[i - 1] - vals[i] > 0]
    if not drops:
        return {"level": "high", "comment": "无明显回落，情绪未平复"}
    mx = max(drops)
    return {"level": _level(mx, 0.15, 0.45), "max_delta": round(mx, 3),
            "comment": "情绪回落后平复的快慢（越大越慢）"}


def _inertia(vals, base):
    """惯性：偏离基线后是否快速回归。统计偏离基线(|v-base|>0.3)的连续段数。"""
    runs = 0
    in_run = False
    for v in vals:
        if abs(v - base) > 0.3:
            if not in_run:
                runs += 1
                in_run = True
        else:
            in_run = False
    return {"displacement_runs": runs, "level": _level(runs, 0, 3),
            "comment": "偏离基线后回归的难易（段数越多越易偏离）"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", required=True, help="LLM 标记层产出的 emotion_annotation.json")
    ap.add_argument("--out", default="./output")
    args = ap.parse_args()

    with open(args.annotation, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = {"files": [], "method": {
        "name": "UED 简化版（VAD 三维 + 6 动态指标）",
        "annotation": "LLM 标记层逐段标注 VAD",
        "limitation": "定性指标为启发式，仅作粗粒度参考，不能替代细读的情感解读",
    }}

    for f in data.get("files", []):
        metrics = calc_metrics(f.get("segments", []))
        result["files"].append({
            "file": f.get("file", "?"),
            "metrics": metrics,
        })

    out_path = out_dir / "emotion_dynamics.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] UED 指标计算 -> {out_path}")
    for f in result["files"]:
        m = f["metrics"]
        if m:
            hb = m["home_base"]
            print(f"  {f['file']}: home_base(v={hb['valence']}, a={hb['arousal']}), "
                  f"variability={m['variability']['valence']}, density={m['density']}")
        else:
            print(f"  {f['file']}: 无标注段")


if __name__ == "__main__":
    main()
