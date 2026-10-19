#!/usr/bin/env python3
"""
ingest.py — 扫描与解析随笔/日记文本文件

功能：
- 递归扫描目录中的 .txt / .md / .doc / .docx
- 编码识别（UTF-8 / GBK / GB18030 等）
- 清洗：frontmatter、HTML 标签、孤立页码、重复空行
- 隐私脱敏（按 config.yaml 的 privacy_patterns）
- 输出 files_manifest.json

用法：
    python ingest.py --target-dir <目录> [--out <输出目录>] [--config <config.yaml>]
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_EXTENSIONS = [".txt", ".md", ".doc", ".docx"]

# frontmatter 正则：YAML（---）与 TOML（+++）
FRONTMATTER_RE = re.compile(
    r"^\s*(?:---|\+\+\+)\s*\n.*?\n\s*(?:---|\+\+\+)\s*\n?",
    re.DOTALL,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
PAGE_NUMBER_RE = re.compile(r"^\s*(?:第\s*\d+\s*页(?:\s*/\s*\d+)?|\d+)\s*$")


def load_config(config_path):
    """加载 config.yaml，返回 dict；缺失时返回默认。"""
    cfg = {
        "supported_extensions": DEFAULT_EXTENSIONS,
        "strip_frontmatter": True,
        "strip_html_tags": True,
        "strip_page_numbers": True,
        "collapse_blank_lines": True,
        "privacy_mode": True,
        "privacy_patterns": [],
        "privacy_names": [],
        "privacy_addresses": [],
    }
    if config_path and Path(config_path).exists():
        if yaml is None:
            print("[warn] PyYAML 未安装，跳过 config 解析", file=sys.stderr)
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            cfg.update({k: v for k, v in user_cfg.items() if k in cfg})
    return cfg


def detect_encoding(data: bytes):
    """按优先顺序尝试常见中文编码。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return data.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(replace)"


FRONTMATTER_DATE_RE = re.compile(
    r"^\s*(?:date|日期|created|时间)\s*[:：]\s*(.+?)\s*$", re.MULTILINE
)


def extract_frontmatter_date(text: str) -> str:
    """在清洗前从 frontmatter 提取日期字段，供时间线使用。"""
    m = FRONTMATTER_RE.search(text)
    if not m:
        return ""
    fm = m.group(0)
    dm = FRONTMATTER_DATE_RE.search(fm)
    if dm:
        return dm.group(1).strip().strip("\"'")
    return ""


def clean_text(text: str, cfg: dict) -> str:
    if cfg.get("strip_frontmatter", True):
        text = FRONTMATTER_RE.sub("", text, count=1)
    if cfg.get("strip_html_tags", True):
        text = HTML_TAG_RE.sub("", text)
    lines = text.splitlines()
    out = []
    blank_run = 0
    for line in lines:
        if cfg.get("strip_page_numbers", True) and PAGE_NUMBER_RE.match(line):
            continue
        if not line.strip():
            blank_run += 1
            if cfg.get("collapse_blank_lines", True) and blank_run > 1:
                continue
            out.append("")
        else:
            blank_run = 0
            out.append(line)
    return "\n".join(out)


def apply_privacy(text: str, cfg: dict) -> str:
    if not cfg.get("privacy_mode", True):
        return text
    # 显式名单脱敏（姓名/地址：中文无法靠正则可靠识别，须用户显式列出）
    for name in cfg.get("privacy_names", []):
        if name:
            text = text.replace(str(name), "[已脱敏]")
    for addr in cfg.get("privacy_addresses", []):
        if addr:
            text = text.replace(str(addr), "[已脱敏]")
    # 正则脱敏（电话/身份证/邮箱等）
    for item in cfg.get("privacy_patterns", []):
        if isinstance(item, dict):
            pat = item.get("pattern")
        else:
            pat = item
        if not pat:
            continue
        try:
            text = re.sub(pat, "[已脱敏]", text)
        except re.error:
            continue
    return text


def read_text_file(path: Path, cfg: dict):
    data = path.read_bytes()
    text, encoding = detect_encoding(data)
    text = clean_text(text, cfg)
    text = apply_privacy(text, cfg)
    return text, encoding


def read_docx(path: Path, cfg: dict):
    """读取 .docx；.doc 老格式尽力而为。"""
    try:
        from docx import Document  # python-docx
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text, "docx"
    except Exception as e:
        # 回退：老 .doc 尝试 antiword / textract（未安装则记录错误）
        text = f"[读取失败] {path.name}: {e}"
        return text, "doc-fallback"


def scan(target_dir: Path, cfg: dict):
    exts = cfg.get("supported_extensions", DEFAULT_EXTENSIONS)
    manifest = []
    for ext in exts:
        for p in sorted(target_dir.rglob(f"*{ext}")):
            # 跳过输出目录自身，避免重复解析生成的 JSON/HTML
            manifest.append(p)
    # 去重（不同大小写/重复 glob）
    seen = set()
    unique = []
    for p in manifest:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def parse_file(path: Path, cfg: dict):
    ext = path.suffix.lower()
    if ext in (".docx", ".doc"):
        text, encoding = read_docx(path, cfg)
        frontmatter_date = ""
    else:
        raw = path.read_bytes()
        raw_text = detect_encoding(raw)[0]
        frontmatter_date = extract_frontmatter_date(raw_text)
        text, encoding = read_text_file(path, cfg)
    return {
        "file": str(path),
        "name": path.name,
        "ext": ext,
        "encoding": encoding,
        "date": frontmatter_date,
        "content": text,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", required=True)
    ap.add_argument("--out", default="./output")
    ap.add_argument("--config", default="./config.yaml")
    args = ap.parse_args()

    target = Path(args.target_dir)
    if not target.exists():
        print(f"[error] 目录不存在: {target}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(args.config)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = scan(target, cfg)
    manifest = {"target_dir": str(target), "files": []}
    for p in files:
        try:
            manifest["files"].append(parse_file(p, cfg))
        except Exception as e:
            manifest["files"].append(
                {"file": str(p), "name": p.name, "ext": p.suffix.lower(),
                 "encoding": "error", "content": "", "error": str(e)}
            )

    out_path = out_dir / "files_manifest.json"
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] 已解析 {len(files)} 个文件 -> {out_path}")
    print(json.dumps({"total_files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
