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
            # 只收已知键：配置里拼错的名字不该悄悄改掉默认行为
            cfg.update({k: v for k, v in user_cfg.items() if k in cfg})
    return cfg


def detect_encoding(data: bytes):
    """按顺序逐个试解码。

    UTF-8 必须排在前面：GB18030 几乎能吞下任意字节序列，放在前面会把 UTF-8 正文读成乱码。
    """
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
    """日期必须在清洗之前取走，frontmatter 随后会被整段删掉。"""
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
    # 姓名与地址没法用正则可靠识别，只能按用户给出的名单逐个替换
    for name in cfg.get("privacy_names", []):
        if name:
            text = text.replace(str(name), "[已脱敏]")
    for addr in cfg.get("privacy_addresses", []):
        if addr:
            text = text.replace(str(addr), "[已脱敏]")
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
    try:
        from docx import Document  # python-docx
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text, "docx"
    except Exception as e:
        # 单篇读不出来不该中断整批扫描，把失败原因留在清单里便于回头排查
        text = f"[读取失败] {path.name}: {e}"
        return text, "doc-fallback"


def scan(target_dir: Path, cfg: dict):
    exts = cfg.get("supported_extensions", DEFAULT_EXTENSIONS)
    manifest = []
    for ext in exts:
        for p in sorted(target_dir.rglob(f"*{ext}")):
            manifest.append(p)
    # 扩展名列表里可能有重复项，同一路径只收一次
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
