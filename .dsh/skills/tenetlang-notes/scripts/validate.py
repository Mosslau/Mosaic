#!/usr/bin/env python3
"""tenetlang-notes 场景 D 的自动检查脚本。

把「完成度检查」第 1~3 步（存在性 + 格式）与第 4 步中的格式类核对变成一条命令，
避免每次执行时现场重写检测逻辑（人肉检查易误报：代码块内的 # 注释、非英文错误信息等）。

用法（在仓库根执行）：
    python3 .dsh/skills/tenetlang-notes/scripts/validate.py
    python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links
    python3 .dsh/skills/tenetlang-notes/scripts/validate.py --lang c
    python3 .dsh/skills/tenetlang-notes/scripts/validate.py --deep

覆盖范围（存在性 + 格式）：
    - roadmap ↔ ph 目录双向核对、四层交付物存在性、题解数量对应
    - 主文档 7 章齐全、单一 H1、标题前后空行、章节空壳
    - 相对链接可解析（含 ../ 跨阶段链接）
    - 建设状态断言与磁盘核对：断言「待建」的阶段必须真的不存在

不覆盖（仍需人工深检，见 SKILL.md 场景 D 第 4 步）：
    知识点覆盖、教学增量、代码是否正确、「待建」之外的契约定性描述、「已验证」证据是否属实。
--deep 只把「需要人工核对的漂移项」列出来，不做判定。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量

SKIP_DIRS = {"target", "build", "node_modules", ".git", "__pycache__"}
SKIP_SUFFIXES = (".lock",)
SKIP_NAMES = {
    "CHANGELOG.md", "LICENSE", "NOTICE", "NOTICES.md",
    "package-lock.json", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock", "go.sum",
}
CACHE_PREFIX = (".pytest_cache", ".ruff_cache", ".mypy_cache", ".cache", ".tox")

CHAPTERS = ["概述", "来源与演变", "语法与参数", "底层原理", "使用场景", "代码示例", "总结"]
SEVEN = [f"## {i}. {name}" for i, name in enumerate(CHAPTERS, 1)]
SECTION_ANCHORS = ["### 目标", "### 学习内容", "### 必会概念", "### 示例",
                   "### 练习", "### 阶段验收", "### 推荐项目"]
SUMMARY_SECTIONS = ["### 关键要点", "### 阶段验收清单", "### 动手练习", "### 阶段项目", "### 下一阶段"]

# --deep 用的漂移项模式
BARE_VERIFIED = re.compile(r"已验证(?![：:，,]?\s*\S)")
LINE_REF = re.compile(r"[\w./-]+\.\w{1,6}:\d+")
VERSION_CLAIM = re.compile(r"(?:Apple clang|clang|gcc|g\+\+|go1?|rustc|Python|OpenJDK|javac)\s*\d+\.\d+(?:\.\d+)?")

# 建设状态断言：「待建」类措辞后引用的阶段编号，必须与磁盘（phNN 目录）一致。
# 阶段落地后旧的「目录待建」断言就成了假事实——这是「README 与实现契约一致性」里可自动判定的一类。
BUILD_CLAIM = re.compile(r"(?:目录待建|待建|仍在规划|尚未创建)")
SECTION_REF = re.compile(r"第\s*(\d+(?:\s*[~～\-、,，/]\s*\d+)*)\s*节")
# 只认独立的 phNN（排除 ../ph17-mq-search/ 这类路径与 ph17-foo 这类目录名）
PH_REF = re.compile(r"(?<![\w/])ph(\d{1,2})(?![\d-])")

# 提交纪律：这些文件名/后缀落在未跟踪或已修改项里，几乎一定是构建产物误入提交
ARTIFACT_SUFFIX = (".o", ".obj", ".dSYM", ".log", ".class", ".jar", ".pyc", ".so", ".dylib", ".a", ".exe")
# 带轮转序号的日志（app.log.7）等：按「名字片段」而非后缀判定
ARTIFACT_INFIX = (".log.", ".dSYM/", "/build/", "/target/")
ARTIFACT_DIRS = {"build", "target", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
ARTIFACT_NAMES = {"a.out", "kvlog", "wal_tool", "test_buffer", "logdemo", "file_sync"}
TEXT_SUFFIX = {".md", ".py", ".c", ".h", ".cpp", ".hpp", ".go", ".java", ".rs", ".txt",
               ".toml", ".json", ".yml", ".yaml", ".xml", ".properties", ".sql", ".sh", ".cfg", ".ini",
               # 文档站（website/）的源文件格式
               ".vue", ".css", ".mjs", ".mts", ".ts", ".js", ".svg", ".markdown"}
# 无扩展名但确实是源码/文档的常见文件名，避免误报
SOURCE_NAMES = {"Makefile", "Dockerfile", "LICENSE", "NOTICE", "README", "CHANGELOG",
                "CMakeLists.txt", "go.mod", "go.sum", "Cargo.lock", "compose.yaml"}

problems: list[str] = []
warnings: list[str] = []


def is_governed(path: Path) -> bool:
    """该文件是否归本 skill 管辖（排除生成物/缓存/第三方）。"""
    parts = path.parts
    if any(p in SKIP_DIRS or p.startswith(CACHE_PREFIX) for p in parts):
        return False
    if path.name in SKIP_NAMES or path.name.endswith(SKIP_SUFFIXES):
        return False
    return path.suffix == ".md"


def strip_fences(lines: list[str]) -> list[bool]:
    """返回每行是否位于代码围栏内（围栏行本身也算「内」，避免误判）。"""
    infence, out = False, []
    for line in lines:
        if line.lstrip().startswith("```"):
            out.append(True)
            infence = not infence
            continue
        out.append(infence)
    return out


def mask_inline(line: str) -> str:
    """把行内代码 `...` 的内容抹成同长度空白，避免把其中的 () 误判为链接。"""
    out, i, n = [], 0, len(line)
    while i < n:
        if line[i] == "`":
            j = line.find("`", i + 1)
            if j == -1:
                out.append(line[i:])
                break
            out.append(" " * (j - i + 1))
            i = j + 1
        else:
            out.append(line[i])
            i += 1
    return "".join(out)


def visible_lines(lines: list[str]) -> list[str]:
    """代码围栏外的行，且行内代码已被抹除——所有链接检查都基于它。"""
    fences = strip_fences(lines)
    return ["" if fences[i] else mask_inline(l) for i, l in enumerate(lines)]


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- 各项检查

def check_links(root: Path, files: list[Path]) -> None:
    """解析全部相对链接（./ 与 ../）并检查目标是否存在。"""
    link_re = re.compile(r"\]\((?!#)([^)\s]+)\)")
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
        for i, line in enumerate(visible_lines(lines)):
            for m in link_re.finditer(line):
                target = m.group(1)
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):  # http(s):、mailto:
                    continue
                clean = target.split("#", 1)[0].strip()
                if not clean:
                    continue
                resolved = (f.parent / clean).resolve()
                if not resolved.exists():
                    problems.append(f"{rel(f, root)}:{i + 1}: 悬挂链接 → {target}")


def check_roadmap(root: Path, lang: Path, roadmap: Path) -> None:
    lines = roadmap.read_text(encoding="utf-8").split("\n")
    fences = strip_fences(lines)
    view = visible_lines(lines)

    # H1 唯一
    h1 = [i + 1 for i, l in enumerate(view) if re.match(r"^# ", l)]
    if len(h1) != 1:
        problems.append(f"{rel(roadmap, root)}: H1 数量为 {len(h1)}（应为 1）")

    # 磁盘阶段目录
    dirs = sorted(p for p in lang.glob("ph*") if p.is_dir())
    numbers = []
    for d in dirs:
        m = re.match(r"ph(\d+)-", d.name)
        if not m:
            problems.append(f"{rel(d, root)}: 目录名不符合 ph<NN>-<主题>")
            continue
        numbers.append(int(m.group(1)))
        # 主文档
        docs = [p for p in d.glob("*.md") if p.name != "README.md"]
        if not docs:
            problems.append(f"{rel(d, root)}: 缺主文档 <NN>-<主题>.md")
        for layer in ("examples", "exercises", "project"):
            if not (d / layer).is_dir():
                problems.append(f"{rel(d, root)}: 缺 {layer}/")

    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"{rel(lang, root)}: 阶段编号不连续 {numbers}")

    # roadmap 声明的阶段数 vs 目录数
    declared = [l for l in view if re.match(r"^## \d+\. ", l)]
    if len(declared) != len(dirs):
        problems.append(
            f"{rel(roadmap, root)}: roadmap 声明 {len(declared)} 个阶段，磁盘有 {len(dirs)} 个 ph 目录")

    # 📖 链接行与目录对齐
    for i, l in enumerate(view):
        if not l.strip().startswith(">"):
            continue
        m = re.search(r"\]\((\./ph[^)\s]+)\)", l)
        if m and not (roadmap.parent / m.group(1).split("#")[0]).exists():
            problems.append(f"{rel(roadmap, root)}:{i + 1}: 📖 链接目标不存在 → {m.group(1)}")


def check_phase_doc(root: Path, doc: Path) -> None:
    lines = doc.read_text(encoding="utf-8").split("\n")
    fences = strip_fences(lines)
    view = visible_lines(lines)

    # 单一 H1
    h1 = [i + 1 for i, l in enumerate(view) if re.match(r"^# ", l)]
    if len(h1) != 1:
        problems.append(f"{rel(doc, root)}: H1 数量为 {len(h1)}（应为 1）")

    # 7 章齐全（顺序按出现顺序核对）
    found_titles = [l.strip() for l in view if re.match(r"^## \d+\. ", l)]
    if found_titles != SEVEN:
        problems.append(f"{rel(doc, root)}: 7 章不齐或顺序不符 → {found_titles}")

    # 第 7 章必查小节
    for sec in SUMMARY_SECTIONS:
        if not any(l.startswith(sec) for l in view):
            problems.append(f"{rel(doc, root)}: 缺第 7 章小节「{sec}」")

    # 边界声明与基线说明（存在性，不做语义判断）
    body = "\n".join(view)
    if "不涉及" not in body:
        problems.append(f"{rel(doc, root)}: 第 1 章缺边界声明（未出现「不涉及」）")
    if "为基线" not in body:
        problems.append(f"{rel(doc, root)}: 第 2 章缺基线说明（未出现「为基线」）")

    for i, l in enumerate(lines):
        if fences[i]:
            continue
        # 标题前后空行（标题后直接跟代码围栏不算违规——围栏自带视觉分隔）
        if re.match(r"^#{1,6} ", l):
            if i > 0 and lines[i - 1].strip() != "":
                problems.append(f"{rel(doc, root)}:{i + 1}: 标题前缺空行")
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt.strip() != "" and not nxt.lstrip().startswith("```"):
                    problems.append(f"{rel(doc, root)}:{i + 1}: 标题后缺空行")
        # 空章节（同级或更高级标题紧随其后且中间无正文）
        m = re.match(r"^(#{2,4}) ", l)
        if m:
            lvl = len(m.group(1))
            nxt = [x for x in lines[i + 1:i + 4] if x.strip()]
            if nxt:
                m2 = re.match(r"^(#{2,4}) ", nxt[0])
                if m2 and len(m2.group(1)) <= lvl:
                    problems.append(f"{rel(doc, root)}:{i + 1}: 空章节「{l.strip()}」")


def check_phase_code(root: Path, d: Path) -> None:
    """题解数量对应（只查数量，不查内容）。"""
    ex = d / "exercises"
    if not ex.is_dir():
        return
    sols = [p for p in ex.iterdir() if p.name.startswith("sol-") and p.name != "README.md"]
    if sols and not (ex / "README.md").exists():
        problems.append(f"{rel(ex, root)}: 有 sol-* 但缺 README.md（题目）")
    readme = ex / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        asked = len(re.findall(r"^## 练习\s*\d+", text, re.M))
        if asked and len(sols) != asked:
            warnings.append(
                f"{rel(ex, root)}: 题目 {asked} 道 vs 参考实现 {len(sols)} 份（一题多解请用 sol-05a/sol-05b 命名）")


def expand_sections(spec: str) -> list[int]:
    """展开「18~23」「22/23」「16」这类节号写法为整数列表。"""
    out: list[int] = []
    for part in re.split(r"[、,，/]", spec):
        part = part.strip()
        rng = re.fullmatch(r"(\d+)\s*[~～\-]\s*(\d+)", part)
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
            if lo <= hi:
                out.extend(range(lo, hi + 1))
        elif part.isdigit():
            out.append(int(part))
    return out


def check_build_status(root: Path, lang_root: Path, files: list[Path]) -> None:
    """建设状态断言：文档说「待建」的阶段，磁盘上必须真的不存在。

    这是「README 与实现契约一致性」里可自动判定的一类。阶段建成后旧的
    「目录待建」断言会变成假事实，所以它与实现漂移是同一个缺陷：文档描述
    的对象已经变了。反向不检查——阶段未写成「待建」不等于它必须被提到。

    引用解析优先取「第 N 节」（本仓库唯一权威的节号体系），仅在整行没有节号时
    才退回 phNN。否则「ph17 已落地，roadmap 第 18~23 节仍在规划中」会因为行内
    出现已建成的 ph17 而误报。
    """
    on_disk: dict[str, dict[int, str]] = {}
    for lang_dir in sorted(p for p in lang_root.iterdir() if p.is_dir()):
        found: dict[int, str] = {}
        for d in sorted(lang_dir.glob("ph*")):
            m = re.match(r"ph(\d+)-", d.name)
            if d.is_dir() and m:
                found[int(m.group(1))] = d.name
        on_disk[lang_dir.name] = found

    for f in files:
        parts = f.relative_to(lang_root).parts
        lang = parts[0] if parts else ""
        if lang not in on_disk:
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
        fences = strip_fences(lines)
        for i, line in enumerate(visible_lines(lines)):
            if fences[i] or not BUILD_CLAIM.search(line):
                continue
            tag = f"{rel(f, root)}:{i + 1}"
            sections: list[int] = []
            for m in SECTION_REF.finditer(line):
                sections.extend(expand_sections(m.group(1)))
            if sections:
                targets = sorted(set(sections))
            else:
                targets = sorted({int(n) for n in PH_REF.findall(line)})
            if not targets:
                warnings.append(f"{tag}: 建设状态断言未给出阶段编号，无法自动核对 → 请人工与磁盘比对")
                continue
            for n in targets:
                if n in on_disk[lang]:
                    problems.append(
                        f"{tag}: 断言「待建」的阶段已建成 → {lang}/{on_disk[lang][n]}"
                        "（假事实：阶段落地后应清除该断言）")


def check_deep(root: Path, files: list[Path]) -> None:
    """只列出需人工核对的漂移项，不做判定。"""
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
        fences = strip_fences(lines)
        view = visible_lines(lines)
        for i, l in enumerate(lines):
            if fences[i]:
                continue
            tag = f"{rel(f, root)}:{i + 1}"
            if BARE_VERIFIED.search(view[i]) and "：" not in view[i] and ":" not in view[i]:
                warnings.append(f"{tag}: 疑似裸「已验证」（需补命令 + 输入 + 结果）")
            if LINE_REF.search(view[i]):
                warnings.append(f"{tag}: 行号引用 → {LINE_REF.search(view[i]).group(0)}（源码编辑后易漂移）")
            if VERSION_CLAIM.search(view[i]):
                warnings.append(f"{tag}: 版本声明 → {VERSION_CLAIM.search(view[i]).group(0)}（请与 --version 实测比对）")


def looks_like_artifact(rel_path: str, real: Path | None = None) -> bool:
    p = Path(rel_path)
    name = p.name
    if name in ARTIFACT_NAMES or name in SOURCE_NAMES:
        return name in ARTIFACT_NAMES
    if any(part in ARTIFACT_DIRS for part in p.parts):
        return True
    if p.suffix in ARTIFACT_SUFFIX:
        return True
    # 轮转日志 / dSYM 包内文件等：路径中段命中
    if any(frag in "/" + rel_path for frag in ARTIFACT_INFIX):
        return True
    # 无扩展名但带可执行位的文件（go build 产物、手工编译的 demo）
    if p.suffix == "" and real is not None and real.is_file() and os.access(real, os.X_OK):
        return True
    return False


def is_binary_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIX:
        return False
    try:
        with path.open("rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    if b"\0" in head:
        return True
    if not head:
        return False
    # 按「字符」而非「字节」统计可打印率：本仓库注释大量使用中文，UTF-8 下每个汉字占 3 字节
    # 且全部 >= 0x80，按字节算可打印率会掉到 0.8 以下，把纯文本源码误判成二进制。
    # errors="replace" 兜住「4096 字节截断在多字节字符中间」的情况。
    text = head.decode("utf-8", errors="replace")
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\t\n\r")
    return printable / len(text) < 0.85


def check_git(root: Path) -> bool:
    """分支/远程同步 + 提交前变更集核对。返回 True 表示 git 检查已完成。"""
    git = shutil.which("git")
    if git is None or not (root / ".git").exists():
        warnings.append("未检测到 git 仓库，跳过分支/提交检查")
        return False

    def run(*args: str) -> str:
        try:
            out = subprocess.run([git, *args], cwd=root, capture_output=True, text=True, timeout=30)
            return out.stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    # 分支与远程同步状态
    branch = run("rev-parse", "--abbrev-ref", "HEAD").strip() or "(unknown)"
    sha = run("rev-parse", "--short", "HEAD").strip()
    upstream = run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    if upstream:
        counts = run("rev-list", "--left-right", "--count", f"{upstream}...HEAD").strip().split()
        if len(counts) == 2:
            behind, ahead = counts[0], counts[1]
            if behind != "0":
                problems.append(
                    f"{branch}: 落后 {upstream} {behind} 个提交——先同步再跑完成度检查，否则基线可能是旧的")
            elif ahead != "0":
                warnings.append(f"{branch}: 领先 {upstream} {ahead} 个提交（尚未推送）")
        print(f"基线：{branch} @ {sha}（upstream={upstream}）")
    else:
        warnings.append(f"{branch}: 无 upstream（未跟踪远程分支），无法判断是否落后于 origin")

    # 变更集核对：未跟踪 + 已修改项里的构建产物
    porcelain = run("status", "--porcelain", "--untracked-files=all")
    for raw in porcelain.splitlines():
        if len(raw) < 4:
            continue
        code, path = raw[:2], raw[3:].strip().strip('"')
        if code.startswith("??"):
            p = root / path
            if looks_like_artifact(path, p):
                problems.append(
                    f"未跟踪但疑似构建产物 → {path}"
                    + ("（二进制）" if p.is_file() and is_binary_file(p) else "")
                    + "；确认 .gitignore 已覆盖再提交")
        elif "M" in code:
            p = root / path
            if p.is_file() and is_binary_file(p):
                problems.append(f"已修改的二进制/日志被 git 跟踪 → {path}；应「移除 + 补 .gitignore」")
    return True


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="tenetlang-notes 场景 D 自动检查")
    ap.add_argument("--lang", help="只检查某门语言（目录名，如 c / cpp / rs）")
    ap.add_argument("--links", action="store_true", help="只检查相对链接")
    ap.add_argument("--git", action="store_true", help="只做分支/远程同步与提交前变更集核对")
    ap.add_argument("--deep", action="store_true", help="额外列出需人工核对的漂移项")
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    lang_root = root / "languages" / "studies"
    if not lang_root.is_dir():
        print(f"找不到 {lang_root}，请从仓库根执行", file=sys.stderr)
        return 2

    langs = sorted(p for p in lang_root.iterdir() if p.is_dir())
    if args.lang:
        langs = [p for p in langs if p.name == args.lang]
        if not langs:
            print(f"找不到语言目录 {lang_root / args.lang}", file=sys.stderr)
            return 2

    # 该语言目录下受管辖的 md（按语言归属去重）
    all_md = [p for p in sorted(lang_root.rglob("*.md")) if is_governed(p)]
    lang_md: dict[Path, list[Path]] = {}
    for lang in langs:
        lang_md[lang] = [p for p in all_md if p == lang or lang in p.parents]

    governed = [p for paths in lang_md.values() for p in paths]

    # roadmap：该语言目录下的顶层 md（py/python.md、rs/rust.md 皆可）
    roadmaps = [p for p in lang_root.glob("*/*.md") if p.parent in langs and p.name != "README.md"]

    if args.links:
        check_links(root, governed)
    elif args.git:
        check_git(root)
    else:
        for rm in roadmaps:
            check_roadmap(root, rm.parent, rm)
        for doc in governed:
            if doc.parent.name.startswith("ph"):
                check_phase_doc(root, doc)
                check_phase_code(root, doc.parent)
        check_links(root, governed)
        check_build_status(root, lang_root, governed)
        if args.deep:
            check_deep(root, governed)

    print(f"检查范围：{len(governed)} 个受管辖 .md（{len(langs)} 门语言）、{len(roadmaps)} 份 roadmap\n")
    for w in warnings:
        print(f"[需人工核对] {w}")
    if warnings:
        print()
    for p in problems:
        print(f"[问题] {p}")
    print()
    print(f"汇总：{len(problems)} 个问题，{len(warnings)} 条需人工核对")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
