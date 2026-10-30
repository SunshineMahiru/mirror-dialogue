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

# frontmatter 只认文件开头的分隔块，且闭合分隔符必须出现在前 40 行内；
# 正文中间的 --- 是分隔线，不能当作元数据边界
FRONTMATTER_LIMIT = 40

HTML_TAG_RE = re.compile(r"<[^>]+>")

# 只删真正的页码行；纯数字行可能是年份标题或编号条目，不能删
PAGE_NUMBER_RE = re.compile(r"^\s*第\s*\d+\s*页(?:\s*/\s*\d+)?\s*$")


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


def _looks_like_frontmatter(lines) -> bool:
    """至少要有 key: value 形式的元数据行，纯正文块不能当 frontmatter 删掉。"""
    seen = False
    for line in lines:
        if not line.strip():
            continue
        if not re.match(r"^\s*[\w\u4e00-\u9fff.-]+\s*[:：]", line):
            return False
        seen = True
    return seen


def split_frontmatter(text: str):
    """把文件开头的 frontmatter 与正文分开。

    只接受第一行非空内容为 --- 或 +++ 的写法；闭合分隔符必须在前 40 行内出现，
    且块内至少有一条 key: value。找不到这些特征时按普通正文处理，避免把
    分隔线之间的正文整段删掉。
    """
    lines = text.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or lines[start].strip() not in ("---", "+++"):
        return "", text
    delim = lines[start].strip()
    limit = min(len(lines), start + FRONTMATTER_LIMIT + 1)
    for end in range(start + 1, limit):
        if lines[end].strip() == delim:
            block = lines[start + 1:end]
            if not _looks_like_frontmatter(block):
                return "", text
            return "\n".join(block), "\n".join(lines[end + 1:])
    return "", text


def extract_frontmatter_date(text: str) -> str:
    """日期必须在清洗之前取走，frontmatter 随后会被整段删掉。"""
    fm, _ = split_frontmatter(text)
    if not fm:
        return ""
    dm = FRONTMATTER_DATE_RE.search(fm)
    if dm:
        return dm.group(1).strip().strip("\"'")
    return ""


def clean_text(text: str, cfg: dict) -> str:
    if cfg.get("strip_frontmatter", True):
        _, text = split_frontmatter(text)
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


def compile_privacy_patterns(cfg: dict):
    """一次编译隐私正则；写错的正则直接报错，不允许带着未脱敏的正文继续。"""
    patterns = []
    for item in cfg.get("privacy_patterns", []):
        if isinstance(item, dict):
            label = str(item.get("name") or item.get("pattern") or "")
            pat = item.get("pattern")
        else:
            label = str(item)
            pat = item
        if not pat:
            continue
        try:
            patterns.append((label or str(pat), re.compile(str(pat))))
        except re.error as e:
            raise ValueError(f"privacy_patterns 正则无效: {pat!r}: {e}") from e
    return patterns


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
    patterns = cfg.get("_privacy_patterns")
    if patterns is None:
        patterns = compile_privacy_patterns(cfg)
    for _label, pat in patterns:
        text = pat.sub("[已脱敏]", text)
    return text


def read_text_file(path: Path, cfg: dict):
    data = path.read_bytes()
    text, encoding = detect_encoding(data)
    text = clean_text(text, cfg)
    text = apply_privacy(text, cfg)
    return text, encoding


def read_docx(path: Path, cfg: dict):
    if path.suffix.lower() == ".doc":
        raise ValueError("python-docx 不支持旧版 .doc，请另存为 .docx 后重试")
    from docx import Document  # python-docx

    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs)
    # Word 分支同样要经过清洗与脱敏，不能只在文本文件上做
    text = clean_text(text, cfg)
    text = apply_privacy(text, cfg)
    return text, "docx"


def scan(target_dir: Path, cfg: dict, exclude_dirs=()):
    exts = {str(e).lower() for e in cfg.get("supported_extensions", DEFAULT_EXTENSIONS)}
    excluded = []
    for d in exclude_dirs:
        try:
            excluded.append(Path(d).resolve())
        except OSError:
            continue
    found = []
    for p in sorted(target_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if any(ex in resolved.parents for ex in excluded):
            continue
        found.append(p)
    return found


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
    try:
        cfg["_privacy_patterns"] = compile_privacy_patterns(cfg)
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = scan(target, cfg, exclude_dirs=[out_dir])
    manifest = {"target_dir": str(target), "files": []}
    for p in files:
        try:
            manifest["files"].append(parse_file(p, cfg))
        except Exception as e:
            print(f"[warn] 读取失败: {p} ({e})", file=sys.stderr)
            manifest["files"].append(
                {"file": str(p), "name": p.name, "ext": p.suffix.lower(),
                 "encoding": "error", "content": "", "error": str(e)}
            )

    out_path = out_dir / "files_manifest.json"
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = sum(1 for f in manifest["files"] if not f.get("error"))
    print(f"[ok] 已解析 {ok}/{len(files)} 个文件 -> {out_path}")
    print(json.dumps({"total_files": len(files), "parsed": ok}, ensure_ascii=False))


if __name__ == "__main__":
    main()
