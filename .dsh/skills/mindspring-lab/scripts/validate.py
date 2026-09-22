#!/usr/bin/env python3
"""MindSpring 实验/项目存在性与纪律自动检查（mindspring-lab 场景 D 的第 1~2 步）。

用法（在 MindSpring 仓库根执行）：
    python3 .dsh/skills/mindspring-lab/scripts/validate.py            # 全量存在性检查
    python3 .dsh/skills/mindspring-lab/scripts/validate.py --deep     # 额外列出需人工核对的项
    python3 .dsh/skills/mindspring-lab/scripts/validate.py --pytest   # 可选：实跑 pytest
    python3 .dsh/skills/mindspring-lab/scripts/validate.py --git      # 提交前变更集核对

退出码：0 = 无问题，1 = 存在问题（可作提交前门禁）。

覆盖：索引表 ↔ 目录双向核对、状态/日期一致性（algorithms 与 engineering 两线）、
README 六段齐全、占位段检测（✅ 状态下升级为硬伤）、章节锚点有效性、
impl.py 违禁 import 与属性调用扫描、engineering 阶段编号一致性、
✅ 项目验收标准打勾核对。
不管：推导质量、结果分析深度等教学判断——那些按场景 D 第 3 步人工深检。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # .dsh/skills/mindspring-lab/scripts/validate.py -> repo root
assert (ROOT / "algorithms").is_dir(), f"仓库根定位失败：{ROOT}"

ALGO_INDEX = ROOT / "algorithms" / "README.md"
ENG_INDEX = ROOT / "engineering" / "ai-platform" / "README.md"
ALGO_ROADMAP = ROOT / "roadmap" / "人工智能代表算法演进路线.md"

# 六段式权威结构（与 references/ 下两个模板一致；算法实验的"对照"段名按族二选一）
ALGO_SECTIONS_FIXED = ["设计原理", "数学推导", "手写实现要点", "实验结果", "局限与延伸"]
ALGO_SECTIONS_CONTRAST = ["框架对照", "基线对照"]
ENG_SECTIONS = ["目标", "技术栈", "系统架构", "复用的算法实验", "验收标准", "实施笔记"]

# 手写纪律：impl.py 中禁止出现的现成算法接口（framework.py / baseline.py 不受限）
FORBIDDEN_IMPORT_PATTERNS = [
    (re.compile(r"^\s*(from|import)\s+sklearn\b", re.M), "sklearn"),
    (re.compile(r"^\s*(from|import)\s+tensorflow\b", re.M), "tensorflow"),
    (re.compile(r"^\s*(from|import)\s+keras\b", re.M), "keras"),
    (re.compile(r"^\s*(from|import)\s+xgboost\b", re.M), "xgboost"),
    (re.compile(r"^\s*(from|import)\s+lightgbm\b", re.M), "lightgbm"),
    (re.compile(r"^\s*from\s+torch\s+import\s+nn\b", re.M), "torch.nn"),
    (re.compile(r"^\s*(from|import)\s+torch\.nn\b", re.M), "torch.nn"),
    (re.compile(r"^\s*from\s+torch\s+import\s+optim\b", re.M), "torch.optim"),
    (re.compile(r"^\s*(from|import)\s+torch\.optim\b", re.M), "torch.optim"),
    (re.compile(r"^\s*(from|import)\s+torchvision\.models\b", re.M), "torchvision.models"),
]

# 属性调用绕过：`import torch` 后直接用 torch.nn.* 不会出现违禁 import 语句。
# 这类扫描有误报面（字符串/注释中提及），已剔除纯注释行，命中记 🟡 人工确认。
FORBIDDEN_USAGE_PATTERNS = [
    (re.compile(r"\bsklearn\."), "sklearn"),
    (re.compile(r"\btorch\.nn\."), "torch.nn"),
    (re.compile(r"\btorch\.optim\."), "torch.optim"),
    (re.compile(r"\btorchvision\.models\."), "torchvision.models"),
]

CN_NUMERALS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
               "七": 7, "八": 8, "九": 9, "十": 10}

STATUS_RE = re.compile(r"^>\s*状态：([⬜🚧✅])\s*(未开始|进行中|已完成)?（?(\d{4}-\d{2}-\d{2})?）?",
                       re.M)
ANCHOR_RE = re.compile(r"第\s*(\d+(?:\.\d+)+)\s*章")
ENG_STAGE_RE = re.compile(r"对应\s*roadmap\s*阶段：第\s*([一二三四五六七八九十0-9]+)\s*阶段")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+?/?)\)")
# 占位段：整段只有一行模板提示语。兼容全角括号（...）与尖括号 <...> 两种模板占位风格
PLACEHOLDER_RE = re.compile(r"[（<][^\n]{4,}[）>]")


def stage_to_int(text: str) -> int | None:
    """阶段号：兼容中文数字（三）与阿拉伯数字（3）。"""
    if text.isdigit():
        return int(text)
    return CN_NUMERALS.get(text)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)   # 硬伤：不一致 / 违规
    warnings: list[str] = field(default_factory=list)  # 🟡：疑似占位、需人工看
    deep_hints: list[str] = field(default_factory=list)  # --deep 才收集的人工核对项

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def hint(self, msg: str) -> None:
        self.deep_hints.append(msg)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def parse_roadmap_chapters() -> set[str]:
    """从算法演进路线文档提取全部章节号（# / ## / ### 标题的 X.Y.Z 编号）。"""
    chapters: set[str] = set()
    for line in read_text(ALGO_ROADMAP).splitlines():
        m = re.match(r"^#{1,6}\s+(\d+(?:\.\d+)*)\b", line)
        if m:
            chapters.add(m.group(1))
    return chapters


def parse_algo_index(rep: Report) -> dict[str, dict]:
    """解析 algorithms/README.md 索引表：{相对目录: {chapter, status, date}}。

    列序契约（见 references/index-format.md）：实验(链接) | 章节 | 状态 | 完成日期
    表格之外的链接（推荐顺序列表、blockquote 导航）不解析。
    """
    entries: dict[str, dict] = {}
    for lineno, line in enumerate(read_text(ALGO_INDEX).splitlines(), 1):
        if not line.lstrip().startswith("|") or "](" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = LINK_RE.search(cells[0]) if cells else None
        if m is None or len(cells) < 4:
            rep.warn(f"algorithms/README.md 第 {lineno} 行：疑似索引条目但解析失败"
                     f"（列序契约见 references/index-format.md）")
            continue
        link = m.group(2).rstrip("/")
        if not re.match(r"^\d{2}-[\w-]+/[\w-]+$", link):
            rep.warn(f"algorithms/README.md 第 {lineno} 行：链接 {link} 不符合 <NN-族>/<算法名> 形态")
            continue
        entries[link] = {"chapter": cells[1], "status": cells[2], "date": cells[3]}
    return entries


def parse_eng_index(rep: Report) -> dict[str, dict]:
    """解析 engineering/ai-platform/README.md 项目总览表：{目录名: {stage, status, date}}。

    列序契约（见 references/index-format.md）：阶段 | 项目(链接) | 验收标准一句话 | 状态 | 完成日期
    """
    entries: dict[str, dict] = {}
    for lineno, line in enumerate(read_text(ENG_INDEX).splitlines(), 1):
        if not line.lstrip().startswith("|") or "](" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = LINK_RE.search(cells[1]) if len(cells) > 1 else None
        if m is None or len(cells) < 5:
            rep.warn(f"engineering/ai-platform/README.md 第 {lineno} 行：疑似总览条目但解析失败"
                     f"（列序契约见 references/index-format.md）")
            continue
        link = m.group(2).rstrip("/")
        if not re.match(r"^\d{2}-[\w-]+$", link):
            rep.warn(f"engineering/ai-platform/README.md 第 {lineno} 行："
                     f"链接 {link} 不符合 <NN-项目> 形态")
            continue
        entries[link] = {"stage": cells[0], "status": cells[3], "date": cells[4]}
    return entries


def check_status_block(readme: str, rel: str, rep: Report) -> tuple[str, str | None]:
    """校验 README 首行状态声明。返回 (状态符, 日期)。"""
    m = STATUS_RE.search(readme[:800])
    if not m:
        rep.err(f"{rel}：缺少状态声明行（> 状态：⬜/🚧/✅ …）")
        return "?", None
    symbol, word, date = m.group(1), m.group(2), m.group(3)
    expected_word = {"⬜": "未开始", "🚧": "进行中", "✅": "已完成"}[symbol]
    if word and word != expected_word:
        rep.err(f"{rel}：状态符 {symbol} 与文字「{word}」不匹配（应为「{expected_word}」）")
    if symbol == "✅" and not date:
        rep.err(f"{rel}：✅ 必须带完成日期，格式 `> 状态：✅ 已完成（YYYY-MM-DD）`")
    if symbol != "✅" and date:
        rep.warn(f"{rel}：非 ✅ 状态不应带日期")
    return symbol, date


def check_sections(readme: str, rel: str, is_algo: bool, rep: Report,
                   symbol: str) -> None:
    """六段齐全 + 占位段检测。

    力度按状态分级：⬜ 骨架不查占位（本该是空的）；🚧 占位/空段记 🟡；
    ✅ 占位/空段记 ❌——「无占位段落」是 ✅ 门槛，不能软放行。
    """
    headings = set(re.findall(r"^##\s+(.+?)\s*$", readme, re.M))
    required = list(ALGO_SECTIONS_FIXED) if is_algo else list(ENG_SECTIONS)
    for sec in required:
        if not any(h.startswith(sec) for h in headings):
            rep.err(f"{rel}：缺少章节「## {sec}」")
    if is_algo and not any(
        any(h.startswith(c) for h in headings) for c in ALGO_SECTIONS_CONTRAST
    ):
        rep.err(f"{rel}：缺少对照章节（## 框架对照 或 ## 基线对照，按算法族二选一）")

    if symbol == "⬜":
        return
    gate = symbol == "✅"
    report = rep.err if gate else rep.warn
    suffix = "——✅ 门槛要求无空段/占位段" if gate else ""
    for m in re.finditer(r"^##\s+(.+?)\s*\n(.*?)(?=^##\s|\Z)", readme, re.M | re.S):
        title, body = m.group(1), m.group(2).strip()
        if not body:
            report(f"{rel}：章节「{title}」为空{suffix}")
        elif PLACEHOLDER_RE.fullmatch(body):
            report(f"{rel}：章节「{title}」仍是模板占位（整段只有一行提示语）{suffix}")


def find_anchor_line(readme: str, pattern: re.Pattern) -> re.Match | None:
    """锚点只从 blockquote 行（> 开头）中取，防止把正文里的章节引用误当锚点。"""
    for line in readme.splitlines():
        if line.lstrip().startswith(">"):
            m = pattern.search(line)
            if m:
                return m
    return None


def check_verification_claims(readme: str, rel: str, rep: Report) -> None:
    """纪律⑤启发式：出现「已验证」但无任何命令样式——疑似裸写声明。"""
    claims = [
        line for line in readme.splitlines()
        if "已验证" in line and "未在本环境验证" not in line
    ]
    if claims and not any("python" in line or "`" in line for line in claims):
        rep.hint(f"{rel}：出现「已验证」但未见命令/代码样式——是否裸写声明？"
                 f"（纪律⑤要求命令+输入+观察结果三要素）")


def check_algo_unit(unit: Path, idx: dict | None, chapters: set[str], rep: Report,
                    deep: bool) -> None:
    rel = unit.relative_to(ROOT).as_posix()
    readme_path = unit / "README.md"
    readme = read_text(readme_path)
    if not readme:
        rep.err(f"{rel}：缺少 README.md")
        return

    symbol, date = check_status_block(readme, rel, rep)
    check_sections(readme, rel, True, rep, symbol)

    # 章节锚定：有效性（只在 blockquote 行中找）
    anchor = find_anchor_line(readme, ANCHOR_RE)
    if not anchor:
        rep.err(f"{rel}：缺少章节锚点（> 对应文档章节：… 第 X.Y.Z 章）")
    elif anchor.group(1) not in chapters:
        rep.err(f"{rel}：锚定章节 {anchor.group(1)} 在 roadmap 文档中不存在")

    # 索引一致性
    if idx is not None:
        if idx["status"] and idx["status"] != symbol:
            rep.err(f"{rel}：README 状态 {symbol} 与索引表 {idx['status']} 不一致")
        if idx["status"] == "✅" and date and idx["date"] and idx["date"] != date:
            rep.err(f"{rel}：README 日期 {date} 与索引表 {idx['date']} 不一致")
        if idx["status"] == "✅" and not idx["date"]:
            rep.err(f"{rel}：索引表 ✅ 但完成日期为空")
        if anchor and idx["chapter"] and idx["chapter"] != anchor.group(1):
            rep.warn(f"{rel}：索引表章节 {idx['chapter']} 与 README 锚点 {anchor.group(1)} 不一致")

    # 手写纪律：impl.py 违禁 import + 属性调用绕过
    impl = unit / "impl.py"
    if impl.exists():
        src = read_text(impl)
        for pat, lib in FORBIDDEN_IMPORT_PATTERNS:
            if pat.search(src):
                rep.err(f"{rel}/impl.py：违禁 import「{lib}」——核心算法必须手写"
                        f"（对照实现请放 framework.py/baseline.py）")
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )
        for pat, lib in FORBIDDEN_USAGE_PATTERNS:
            if pat.search(code):
                rep.warn(f"{rel}/impl.py：疑似通过属性调用使用「{lib}」"
                         f"（如 import torch 后直接 torch.nn.*）——请人工确认是否绕过手写纪律")
    elif symbol != "⬜":
        rep.warn(f"{rel}：状态 {symbol} 但缺少 impl.py")

    if deep:
        # 需人工核对的漂移/质量项
        result_sec = re.search(r"^##\s*实验结果\s*\n(.*?)(?=^##\s|\Z)", readme, re.M | re.S)
        if result_sec and symbol in ("🚧", "✅"):
            body = result_sec.group(1)
            if not re.search(r"\d", body):
                rep.hint(f"{rel}：「实验结果」段无任何数字——双跑对照是否真跑了？")
            if "复现" not in body:
                rep.hint(f"{rel}：「实验结果」段未写明复现方式")
        if symbol == "✅":
            math_sec = re.search(r"^##\s*数学推导\s*\n(.*?)(?=^##\s|\Z)", readme, re.M | re.S)
            if math_sec and len(math_sec.group(1).strip()) < 50:
                rep.hint(f"{rel}：✅ 但「数学推导」过短——是否存在推导真空？")
            if not (unit / "demo.py").exists():
                rep.hint(f"{rel}：✅ 但缺少 demo.py——双跑对照的入口在哪？"
                         f"（若对照内嵌于其他文件，请在 README「目录形态」段说明）")
            for m in re.finditer(r"\w+\.py:\d+", readme):
                rep.hint(f"{rel}：行号引用「{m.group(0)}」易漂移，改为引用符号/片段内容")
        check_verification_claims(readme, rel, rep)


def check_eng_unit(unit: Path, idx: dict | None, rep: Report, deep: bool) -> None:
    rel = unit.relative_to(ROOT).as_posix()
    readme = read_text(unit / "README.md")
    if not readme:
        rep.err(f"{rel}：缺少 README.md")
        return

    symbol, date = check_status_block(readme, rel, rep)
    check_sections(readme, rel, False, rep, symbol)

    # 阶段编号一致性：目录 NN ↔ 「第 N 阶段」（中文/阿拉伯数字均可）
    dir_num = int(unit.name.split("-", 1)[0])
    m = find_anchor_line(readme, ENG_STAGE_RE)
    if not m:
        rep.err(f"{rel}：缺少阶段锚点（> 对应 roadmap 阶段：第 N 阶段）")
    elif stage_to_int(m.group(1)) != dir_num:
        rep.err(f"{rel}：目录编号 {dir_num:02d} 与「第 {m.group(1)} 阶段」不一致")

    # 索引一致性（状态 + ✅ 日期）
    if idx is not None:
        if idx["status"] and idx["status"] != symbol:
            rep.err(f"{rel}：README 状态 {symbol} 与项目总览表 {idx['status']} 不一致")
        if idx["status"] == "✅" and date and idx["date"] and idx["date"] != date:
            rep.err(f"{rel}：README 日期 {date} 与项目总览表 {idx['date']} 不一致")
        if idx["status"] == "✅" and not idx["date"]:
            rep.err(f"{rel}：项目总览表 ✅ 但完成日期为空")

    # ✅ 门槛：验收标准必须全部打勾
    if symbol == "✅" and re.search(r"^-\s*\[ \]", readme, re.M):
        rep.err(f"{rel}：✅ 但仍有未勾选的验收标准（- [ ]）——✅ 门槛要求全部打勾")

    if deep:
        reuse = re.search(r"^##\s*复用的算法实验\s*\n(.*?)(?=^##\s|\Z)", readme, re.M | re.S)
        if reuse and symbol in ("🚧", "✅"):
            body = reuse.group(1).strip()
            if not body or PLACEHOLDER_RE.fullmatch(body):
                rep.hint(f"{rel}：「复用的算法实验」未填——闭环断了；没有用到的实验也要写明'无'及原因")
            for link in re.findall(r"\]\((\.\./algorithms/[^)]+)\)", body):
                if not (unit / link).resolve().exists():
                    rep.err(f"{rel}：「复用的算法实验」引用了不存在的路径 {link}")
        check_verification_claims(readme, rel, rep)


def check_git() -> list[str]:
    """提交前变更集核对：构建/缓存产物不应进提交。"""
    problems: list[str] = []
    try:
        out = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return [f"git status 执行失败：{e}"]
    bad = re.compile(r"(__pycache__|\.pyc$|\.pytest_cache|\.ruff_cache|\.ipynb_checkpoints"
                     r"|\.pth$|\.ckpt$|\.log$|/dist/|/build/)")
    for line in out.splitlines():
        if bad.search(line):
            problems.append(f"变更集疑似夹带产物：{line.strip()}"
                            f"（先确认 .gitignore 覆盖，再决定是否提交）")
    return problems


def print_baseline() -> None:
    """--deep 末尾打印 git 基线，供场景 D 第 4 步记忆落盘直接引用。"""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        suffix = "（工作区有未提交变更）" if dirty else ""
        print(f"\n📌 基线：{branch} @ {sha}{suffix}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="MindSpring 存在性与纪律检查")
    ap.add_argument("--deep", action="store_true", help="额外列出需人工核对的项")
    ap.add_argument("--pytest", action="store_true", help="实跑 pytest（可选项）")
    ap.add_argument("--git", action="store_true", help="提交前变更集核对")
    args = ap.parse_args()

    rep = Report()
    chapters = parse_roadmap_chapters()
    if not chapters:
        rep.warn(f"无法解析 {ALGO_ROADMAP.relative_to(ROOT)} 的章节号，章节锚定检查被跳过")

    # --- algorithms 线 ---
    algo_idx = parse_algo_index(rep)
    algo_dirs = sorted(
        p for p in ROOT.glob("algorithms/[0-9][0-9]-*/*") if p.is_dir()
    )
    for unit in algo_dirs:
        rel = unit.relative_to(ROOT).as_posix()
        # 索引表链接相对 algorithms/ 目录书写（如 01-search/a-star），pop 时去掉线名前缀
        idx = algo_idx.pop(rel.split("/", 1)[1], None)
        if idx is None:
            rep.err(f"{rel}：目录存在但未在 algorithms/README.md 索引表登记")
        check_algo_unit(unit, idx, chapters, rep, args.deep)
    for rel in algo_idx:
        rep.err(f"algorithms/README.md 索引表登记了 {rel}，但磁盘目录不存在")

    # --- engineering 线 ---
    eng_idx = parse_eng_index(rep)
    for unit in sorted(p for p in ROOT.glob("engineering/ai-platform/[0-9][0-9]-*") if p.is_dir()):
        idx = eng_idx.pop(unit.name, None)
        if idx is None:
            rep.err(f"{unit.relative_to(ROOT)}：目录存在但未在 "
                    f"engineering/ai-platform/README.md 项目总览登记")
        check_eng_unit(unit, idx, rep, args.deep)
    for name in eng_idx:
        rep.err(f"engineering/ai-platform/README.md 项目总览登记了 {name}，但磁盘目录不存在")

    # --- 可选项 ---
    if args.git:
        rep.errors.extend(check_git())

    if args.pytest:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
        if r.returncode == 5:
            rep.warn("pytest 未收集到任何测试（--pytest 模式，跳过判定）")
        elif r.returncode != 0:
            rep.err("pytest 未全部通过（--pytest 模式）")

    # --- 输出 ---
    for msg in rep.errors:
        print(f"❌ {msg}")
    for msg in rep.warnings:
        print(f"🟡 {msg}")
    if args.deep:
        for msg in rep.deep_hints:
            print(f"🔍 [人工核对] {msg}")
    print(f"\n汇总：{len(rep.errors)} 个硬伤，{len(rep.warnings)} 个警告"
          + (f"，{len(rep.deep_hints)} 项待人工核对" if args.deep else ""))
    if args.deep:
        print_baseline()
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
