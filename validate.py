import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# 页面渲染要用的字段；少一个，对应章节就会空着
# 点路径表示嵌套，`[]` 表示只看列表的首个元素
REQUIRED_SCHEMA = {
    "stats.json": {
        "global.total_files": "文件数",
        "global.total_chinese_chars": "总中文字符",
        "global.total_paragraphs": "总段落",
        "global.total_sentences": "总句子",
        "files[].file": "单文件名字段",
    },
    "quotes.json": {
        "total_quotes": "引用总数",
        "density": "引用密度",
        "quotes[].text": "引用文本",
        "quotes[].position": "引用位置",
    },
    "keywords.json": {
        "global[].word": "高频词",
        "tfidf[].word": "TF-IDF 词",
    },
    "timeline.json": {
        "entries[].date_guess": "日期",
        "entries[].sentiment_label": "情感标签",
    },
    "single_analysis.json": {
        "[].file": "文件名",
        "[].summary": "主题概括",
        "[].quotes[].text": "引用片段",
        "[].quotes[].position": "引用位置",
    },
    "global_analysis.json": {
        "theme_clusters[].name": "主题群名",
        "key_findings[]": "重要发现",
    },
    "discipline_analysis.json": {
        "[].discipline": "学科 id",
        "[].name": "学科显示名",
        "[].core_questions[]": "核心问题",
        "[].concepts[].name": "概念名",
        "[].methods": "方法（字符串或数组，模板两者都支持）",
        "[].evidence[]": "原文证据",
        "[].analysis": "解释",
        "[].confidence": "置信度",
        "[].references[]": "文献",
    },
    "cross_discipline.json": {
        "consensus[]": "共识",
        "disagreement[]": "分歧",
        "blindspots[]": "盲点",
        "further_questions[]": "进一步问题",
    },
    "knowledge_sources.json": {
        "records[].discipline": "学科",
        "records[].concept": "概念",
    },
}

# 隐私扫描用固定规则，不跟随 config 变化：脱敏配置被改坏了，这层检查也不能跟着失效
DEFAULT_PRIVACY = {
    "手机号": r"1[3-9]\d{9}",
    "身份证": r"\d{17}[\dXx]",
    "邮箱": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
}


def load_json(path):
    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return None


def get_by_path(obj, path):
    """按点路径取嵌套值。

    `files[].file` 这类写法要先分成 `files` 与 `[]` 两段，否则会当成一个键名去找。
    """
    parts = []
    for tok in path.split("."):
        if tok.endswith("[]") and tok != "[]":
            parts.append(tok[:-2])
            parts.append("[]")
        else:
            parts.append(tok)
    cur = obj
    for part in parts:
        if part == "[]":
            if isinstance(cur, list):
                if not cur:
                    # 空列表同样代表字段存在：模板的 for 循环遇到空列表只会输出空内容
                    return cur
                cur = cur[0]
            else:
                return None
        else:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    return cur


def zh_len(s):
    """汉字个数，深度门槛按它计数（空白与标点不算）。"""
    if not isinstance(s, str):
        return 0
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def flatten(obj) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------------------
# schema.json 缺失或损坏时用下面的默认阈值顶上，检查逻辑不至于整段失效
# ---------------------------------------------------------------------------
DEFAULT_SCHEMA = {
    "depth": {
        "single": {
            "summary": {"min_zh_chars": 1200},
            "mirror_dialogue": {"min_zh_chars": 500},
            "quotes": {"min_count": 5, "require_interpretation": True},
            "required_mirror_fields": [
                "addressee", "pronoun_map", "self_naming_change", "self_talk", "unsaid"],
        },
        "discipline": {
            "analysis": {"min_zh_chars": 1500},
            "eight_elements": [
                "core_questions", "concepts", "methods", "evidence", "analysis",
                "counter_evidence", "confidence", "references"],
        },
        "global": {
            "key_findings": {"min_count": 10, "target": 15},
            "mirror_dialogue_chapter": {
                "min_zh_chars": 1500,
                "required_parts": [
                    "addressee_spectrum", "self_naming_timeline",
                    "self_talk_patterns", "silence_archaeology", "dialogue_ethics"],
            },
        },
        "cross": {
            "multi_explanations": {"min_count": 8},
            "required_fields": ["complementary", "limitations_ethics"],
            "min_list": {"consensus": 1, "further_questions": 1},
        },
    },
    "discipline_evidence": {"min_evidence_per_core": 3},
}

_SCHEMA_CACHE = None


def load_schema():
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    p = Path(__file__).resolve().parent / "schema.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                _SCHEMA_CACHE = json.load(f)
            return _SCHEMA_CACHE
        except Exception:
            pass
    _SCHEMA_CACHE = DEFAULT_SCHEMA
    return _SCHEMA_CACHE


def _sd(key, default):
    d = load_schema().get("depth", {})
    for k in key.split("."):
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def check_content_depth(single, discipline, global_analysis, report):
    """拦住结构齐全、内容单薄的报告：字数只是兜底下限，算不得目标值，也没有上限。

    阈值全部从 schema.json 读取，调整门槛时不必改动代码。
    """
    min_summary = _sd("single.summary.min_zh_chars", 1200)
    min_md = _sd("single.mirror_dialogue.min_zh_chars", 500)
    min_quotes = _sd("single.quotes.min_count", 5)
    min_analysis = _sd("discipline.analysis.min_zh_chars", 1500)
    min_kf = _sd("global.key_findings.min_count", 10)
    if single:
        for a in single:
            fname = a.get("file", "?")
            summ = a.get("summary", "")
            if zh_len(summ) < min_summary:
                report["fail"].append(
                    f"depth: {fname} summary {zh_len(summ)} 字 < {min_summary}（内容过浅）")
            md = a.get("mirror_dialogue", {})
            md_flat = flatten(md)
            if zh_len(md_flat) < min_md:
                report["fail"].append(
                    f"depth: {fname} mirror_dialogue 展开 {zh_len(md_flat)} 字 < {min_md}")
            qs = a.get("quotes", [])
            if len(qs) < min_quotes:
                report["fail"].append(f"depth: {fname} quotes {len(qs)} 条 < {min_quotes}")
            for q in qs:
                if not q.get("interpretation") and not q.get("explanation"):
                    report["fail"].append(f"depth: {fname} 存在无解读的引用「{q.get('text','')[:20]}」")
    if discipline:
        for d in discipline:
            dname = d.get("discipline", d.get("name", "?"))
            analysis = d.get("analysis", "")
            if zh_len(analysis) < min_analysis:
                report["fail"].append(
                    f"depth: {dname} analysis {zh_len(analysis)} 字 < {min_analysis}")
            if not d.get("counter_evidence"):
                report["fail"].append(f"depth: {dname} counter_evidence 为空")
            if not d.get("methods"):
                report["fail"].append(f"depth: {dname} methods 为空")
    if global_analysis:
        kf = global_analysis.get("key_findings", [])
        if len(kf) < min_kf:
            report["fail"].append(f"depth: key_findings {len(kf)} 条 < {min_kf}")
    # 两类产物都在、又没有深度失败，才记一条通过
    if single and discipline:
        if not any(x.startswith("depth:") for x in report["fail"]):
            report["pass"].append("depth: 内容深度门禁全部达标")


def check_schema(data_dir, report):
    for fname, fields in REQUIRED_SCHEMA.items():
        obj = load_json(Path(data_dir) / fname)
        if obj is None:
            report["schema"][fname] = "缺失（build_html 将跳过该章节）"
            report["fail"].append(f"schema: {fname} 缺失")
            continue
        missing = [k for k in fields if get_by_path(obj, k) is None]
        if missing:
            report["schema"][fname] = f"缺失字段: {missing}"
            report["fail"].append(f"schema: {fname} 缺字段 {missing}")
        else:
            report["schema"][fname] = "OK"
            report["pass"].append(f"schema: {fname} 字段齐全")


def check_file_coverage(manifest, single, report):
    if not manifest or not single:
        report["fail"].append("coverage: 缺少 manifest 或 single_analysis，无法核对覆盖")
        return
    m_files = {f.get("name") for f in manifest.get("files", [])}
    s_files = {a.get("file") for a in single}
    missing = m_files - s_files
    if missing:
        report["fail"].append(f"coverage: 以下文件未被逐篇分析 {missing}")
    else:
        report["pass"].append(f"coverage: {len(m_files)} 个文件全覆盖")


def check_quotes_localizable(quotes, report):
    if not quotes:
        return
    bad = [q for q in quotes.get("quotes", [])
           if not q.get("position") or q["position"] == "位置未定位"]
    if bad:
        report["fail"].append(f"quotes: {len(bad)} 条引用无法定位")
    else:
        report["pass"].append(f"quotes: {len(quotes.get('quotes', []))} 条引用均可定位")


def check_discipline_evidence(plan, discipline, min_ev, report):
    if not plan or not discipline:
        report["fail"].append("discipline: 缺少 discipline_plan 或 discipline_analysis")
        return
    core = plan.get("core_disciplines", [])
    # 学科 id 与显示名都可能出现在产物里，两种都要查得到
    by_id = {d.get("discipline", ""): d for d in discipline}
    by_name = {d.get("name", ""): d for d in discipline}
    for did in core:
        d = by_id.get(did) or by_name.get(did)
        if not d:
            report["fail"].append(f"discipline: 核心学科 {did} 无分析结果")
            continue
        n_ev = len(d.get("evidence", []))
        if n_ev < min_ev:
            report["fail"].append(f"discipline: {did} 证据 {n_ev} < {min_ev}")
        else:
            report["pass"].append(f"discipline: {did} 证据 {n_ev} 条达标")
    for d in discipline:
        dname = d.get("discipline", "")
        required = ["core_questions", "concepts", "methods", "evidence", "analysis",
                    "counter_evidence", "confidence", "references"]
        miss = [k for k in required if k not in d]
        if miss:
            report["fail"].append(f"discipline: {dname} 缺八要素字段 {miss}")


def check_references_verified(discipline, plan, report, verify_on=True):
    if not discipline:
        return
    core = set(plan.get("core_disciplines", [])) if plan else set()
    unverified = []
    # 逐个核心学科判定：只看未核验总数，会掩盖某个核心学科一条都没核验的情形
    for d in discipline:
        did = d.get("discipline", "")
        is_core = did in core or d.get("name") in core
        refs = d.get("references", [])
        for r in refs:
            if not r.get("verified"):
                unverified.append((did, r.get("title", "")))
        if is_core and refs and all(not r.get("verified") for r in refs):
            if verify_on:
                report["fail"].append(
                    f"references: 核心学科 {did} 的 {len(refs)} 条文献全部未核验，"
                    "违反「禁止编造/必须可追溯」红线，须联网或本地库核验后重跑"
                )
            else:
                # 离线时无从核验，如实标注「未检索」算不得编造
                report["warn"].append(
                    f"references: 核心学科 {did} 的 {len(refs)} 条文献未核验"
                    "（verify_references 关闭或未联网，只标「未检索，需核验」，不判 fail）"
                )
    if unverified:
        report["warn"].append(
            f"references: {len(unverified)} 条文献未核验（如 {unverified[0] if unverified else ''}），"
            "需标注'未检索，需核验'"
        )
    else:
        report["pass"].append("references: 文献均标注核验状态")


def check_privacy(manifest, report):
    """重新读取原始文件，与脱敏后的正文逐一对照。

    只信 manifest 里的 content 等于自己给自己判卷：原始路径读不到时记 warn，
    让检查范围的缺口暴露出来，不至于悄悄失效。
    """
    if not manifest:
        return
    leaks = []
    skipped = []
    checked = 0
    for f in manifest.get("files", []):
        raw_path = f.get("file") or f.get("path")
        if not raw_path or not Path(raw_path).exists():
            skipped.append(f.get("name") or raw_path or "?")
            continue
        try:
            raw = Path(raw_path).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            skipped.append(f"{f.get('name')}({e})")
            continue
        checked += 1
        masked = f.get("content", "")
        for label, pat in DEFAULT_PRIVACY.items():
            if re.search(pat, raw) and re.search(pat, masked):
                leaks.append(f"{Path(raw_path).name} 脱敏后仍含{label}（脱敏失效）")
    if skipped:
        report["warn"].append(
            f"privacy: {len(skipped)} 个原始文件路径不可达被跳过（如 {skipped[0]}），"
            "隐私检查未覆盖它们，请确认 manifest.file 为绝对路径"
        )
    if leaks:
        report["fail"].append(f"privacy: {leaks}")
    elif checked:
        report["pass"].append(f"privacy: 抽样 {checked} 个原始文件，未发现脱敏失效")
    else:
        report["fail"].append("privacy: 未能读取任何原始文件，隐私检查失效")


def check_degraded(stats, report):
    if not stats:
        return
    method = stats.get("global", {}).get("method", {})
    if method.get("degraded"):
        report["warn"].append(
            "degraded: 统计为降级模式（未安装 jieba），报告需显式标注降级说明"
        )
    else:
        report["pass"].append("degraded: 统计为完整模式（jieba）")


def check_cross_discipline(cross, report):
    """共识与进一步问题至少各一项，避免空报告通过。"""
    if not cross:
        report["fail"].append("cross: 缺少 cross_discipline.json")
        return
    for key in ("consensus", "further_questions"):
        val = cross.get(key)
        if not isinstance(val, list) or len(val) < 1:
            report["fail"].append(f"cross: {key} 为空或缺失（至少 1 项）")
        else:
            report["pass"].append(f"cross: {key} {len(val)} 项")
    for key in ("disagreement", "blindspots"):
        if key not in cross:
            report["fail"].append(f"cross: {key} 字段缺失")
        elif not isinstance(cross[key], list):
            report["fail"].append(f"cross: {key} 非列表")
        elif len(cross[key]) == 0:
            report["warn"].append(f"cross: {key} 为空，请确认是否真的无该内容")


def check_cross_discipline_multi(cross, report):
    """多元解释不足八组、缺少综合模型时，跨学科综合只是一句空话。"""
    if not cross:
        return
    min_me = _sd("cross.multi_explanations.min_count", 8)
    req_fields = _sd("cross.required_fields",
                     ["synthesis_model", "complementary", "limitations_ethics"])
    me = cross.get("multi_explanations")
    n_me = len(me) if isinstance(me, list) else 0
    if n_me < min_me:
        report["fail"].append(f"cross: multi_explanations {n_me} 组 < {min_me}（要求 ≥{min_me} 组多元解释）")
    else:
        report["pass"].append(f"cross: multi_explanations {n_me} 组")
    sm = cross.get("synthesis_model")
    if not isinstance(sm, list) or len(sm) < 1:
        report["fail"].append("cross: synthesis_model 缺失或为空（跨学科综合模型）")
    else:
        report["pass"].append(f"cross: synthesis_model {len(sm)} 行")
    for key in req_fields:
        if key not in cross:
            report["fail"].append(f"cross: {key} 字段缺失")


def check_mirror_dialogue_chapter(global_analysis, report):
    """镜面对话专章是这个 Skill 的核心诉求：五部分缺一或字数不足都不放行。

    字段名写成 mirror_dialogue_overview 时模板匹配不到，专章会渲染成一段空占位，
    读者看到的是完整目录下的空白。
    """
    if not global_analysis:
        report["fail"].append("mirror_dialogue_chapter: 缺少 global_analysis.json")
        return
    mdc = global_analysis.get("mirror_dialogue_chapter")
    if not mdc:
        report["fail"].append(
            "mirror_dialogue_chapter: 缺失（核心诉求不可省略，须为五部分 ≥1500 字；"
            "注意字段名必须是 mirror_dialogue_chapter，不能是 mirror_dialogue_overview）")
        return
    required_parts = _sd("global.mirror_dialogue_chapter.required_parts",
                         ["addressee_spectrum", "self_naming_timeline",
                          "self_talk_patterns", "silence_archaeology", "dialogue_ethics"])
    min_mdc = _sd("global.mirror_dialogue_chapter.min_zh_chars", 1500)
    missing = [p for p in required_parts if p not in mdc]
    if missing:
        report["fail"].append(f"mirror_dialogue_chapter: 缺五部分 {missing}")
    zh = zh_len(flatten(mdc))
    if zh < min_mdc:
        report["fail"].append(f"mirror_dialogue_chapter: 展开 {zh} 字 < {min_mdc}")
    if not missing and zh >= min_mdc:
        report["pass"].append(f"mirror_dialogue_chapter: 五部分齐全，{zh} 字")


def check_single_mirror_fields(single, report):
    """字段名写错时，代词指认与自我称谓变化这两个维度会在页面里静默消失。"""
    if not single:
        return
    required = _sd("single.required_mirror_fields",
                   ["addressee", "pronoun_map", "self_naming_change", "self_talk", "unsaid"])
    for a in single:
        md = a.get("mirror_dialogue", {})
        if not md:
            continue
        fname = a.get("file", "?")
        missing = [k for k in required if k not in md]
        if missing:
            report["fail"].append(f"mirror_dialogue: {fname} 缺字段 {missing}")


def check_html(html_path, report):
    """页面要能被读者直接翻阅：章节锚点、表格、引用块缺一项，翻到那里就是空的。"""
    if not html_path or not Path(html_path).exists():
        report["warn"].append(f"html: {html_path or 'report.html'} 不存在（先跑 build_html 再校验）")
        return
    html = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    sections = re.findall(r'<section\s+id="([^"]+)"', html)
    expected = ["summary", "per-file", "mirror-dialogue", "discipline-analysis",
                "cross-discipline", "global", "conclusion", "stats", "keywords",
                "quotes", "references", "appendix"]
    missing = [s for s in expected if s not in sections]
    if missing:
        report["fail"].append(f"html: 缺少章节 {missing}")
    else:
        report["pass"].append(f"html: {len(sections)} 个章节齐全")
    n_table = html.count("<table")
    n_blockquote = html.count("<blockquote")
    n_details = html.count("<details")
    if n_table == 0:
        report["fail"].append("html: 无表格（统计/词频/引用表缺失）")
    else:
        report["pass"].append(f"html: {n_table} 个表格")
    if n_blockquote == 0:
        report["warn"].append("html: 无 blockquote 引用片段")
    else:
        report["pass"].append(f"html: {n_blockquote} 条 blockquote 引用")
    if n_details == 0:
        report["warn"].append("html: 无 details 折叠章节")
    else:
        report["pass"].append(f"html: {n_details} 个折叠章节")

    # 附录占掉正文一半以上时，读者翻到的就只是一堆统计表
    def _sec_text(sid):
        m = re.search(rf'<section\s+id="{sid}"[^>]*>(.*?)</section>', html, re.DOTALL)
        return m.group(1) if m else ""

    appendix = "".join(_sec_text(s) for s in ("stats", "keywords", "quotes", "references"))
    body = "".join(_sec_text(s) for s in ("per-file", "discipline-analysis", "mirror-dialogue"))
    appendix_chars = len(re.sub(r"<[^>]+>|\s", "", appendix))
    body_chars = len(re.sub(r"<[^>]+>|\s", "", body))
    if body_chars and appendix_chars / body_chars > 0.5:
        report["fail"].append(
            f"stats_ratio: 统计附录 {appendix_chars} 字 / 分析正文 {body_chars} 字 "
            f"= {appendix_chars / body_chars:.2f} > 0.5（统计:分析 > 1:2，报告主体偏统计）")
    elif body_chars:
        report["pass"].append(f"stats_ratio: 附录/正文 = {appendix_chars / body_chars:.2f}（≤ 0.5）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--config", default="./config.yaml")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--html", default="",
                    help="HTML 报告路径；留空则默认 --data-dir/report.html")
    ap.add_argument("--gate-only", action="store_true",
                    help="事前闸门模式：只跑内容检查（跳过 HTML 结构检查），"
                         "供 build_html 前拦截；fail 非空时 exit 1")
    args = ap.parse_args()

    cfg = {}
    if yaml is not None and Path(args.config).exists():
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    min_ev = cfg.get("min_evidence_per_core", 3)
    # 离线时无法核验，allow_network 关闭就自动降为只提示
    verify_on = bool(cfg.get("verify_references", True)) and bool(cfg.get("allow_network", False))

    data_dir = Path(args.data_dir)
    manifest_path = Path(args.manifest) if args.manifest else (data_dir / "files_manifest.json")

    report = {"pass": [], "fail": [], "warn": [], "schema": {}}

    plan = load_json(data_dir / "discipline_plan.json")
    discipline = load_json(data_dir / "discipline_analysis.json")

    check_schema(data_dir, report)
    check_file_coverage(load_json(manifest_path),
                        load_json(data_dir / "single_analysis.json"), report)
    check_quotes_localizable(load_json(data_dir / "quotes.json"), report)
    check_discipline_evidence(plan, discipline, min_ev, report)
    check_references_verified(discipline, plan, report, verify_on)
    check_privacy(load_json(manifest_path), report)
    check_degraded(load_json(data_dir / "stats.json"), report)
    check_cross_discipline(load_json(data_dir / "cross_discipline.json"), report)
    check_cross_discipline_multi(load_json(data_dir / "cross_discipline.json"), report)
    check_content_depth(load_json(data_dir / "single_analysis.json"),
                        discipline,
                        load_json(data_dir / "global_analysis.json"), report)
    check_mirror_dialogue_chapter(load_json(data_dir / "global_analysis.json"), report)
    check_single_mirror_fields(load_json(data_dir / "single_analysis.json"), report)
    # 渲染之前还没有页面可查，闸门只看内容
    if not args.gate_only:
        html_path = args.html or str(data_dir / "report.html")
        check_html(html_path, report)
    else:
        report["meta"] = {"mode": "gate-only", "html_check": "skipped"}

    report["summary"] = {
        "pass": len(report["pass"]),
        "fail": len(report["fail"]),
        "warn": len(report["warn"]),
        "ok": len(report["fail"]) == 0,
    }

    out = data_dir / "validation_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[validate] 校验完成 -> {out}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"  pass {len(report['pass'])} / fail {len(report['fail'])} / warn {len(report['warn'])}")
    for f in report["fail"]:
        print(f"  [FAIL] {f}")
    for w in report["warn"]:
        print(f"  [WARN] {w}")

    sys.exit(0 if report["summary"]["ok"] else 1)


if __name__ == "__main__":
    main()
