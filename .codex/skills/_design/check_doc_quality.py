#!/usr/bin/env python3
"""技术文档质量门校验脚本（配套 .codex/skills 技术文档 skill 家族）。

把各 skill「写作质量门」中可机械判定的部分变成可执行检查，用于交付前自检：

  1. 占位段落   —— 残留以括号包裹的模板提示句
  2. 事实标签   —— 关键结论是否带统一词表中的标签
  3. 无来源数字 —— 被报告的数字是否临近可追溯的命令/脚本/标签
  4. 预期输出标记 —— 代码块中的输出是否标注 [固定] / [随环境/版本变化]

用法:
    python3 check_doc_quality.py <文件或目录> [...]
    python3 check_doc_quality.py --json docs/
    python3 check_doc_quality.py --only placeholder docs/

退出码: 0 = 无 error；1 = 存在 error（warning 不影响退出码）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# 统一事实标签词表，见 _design/technical-doc-skills-design.md
FACT_LABELS = [
    "源码确认",
    "运行确认",
    "规范确认",
    "文档确认",
    "设计意图",
    "未验证",
]
LABEL_ALT = "|".join(FACT_LABELS)

# 「不适用」是允许的通过结果
NOT_APPLICABLE = "不适用"

# 以全角/半角括号开头的整段，视为模板占位提示句
PLACEHOLDER_RE = re.compile(r"^\s*[（(][^）)]{6,}[）)]\s*$")

# 统一词表之外的旧标签，出现即提示收敛
LEGACY_LABELS = [
    "尚未实测",
    "尚未验证",
    "生产验证",
    "测试环境验证",
    "迁移文件确认",
    "ORM 确认",
    "契约文件确认",
]

# 数字形态：整数/小数/倍数/百分比/毫秒等
NUMBER_RE = re.compile(r"(?<![\w.\-/])(\d+(?:\.\d+)?)\s*(%|ms|us|µs|ns|s\b|MB|GB|KB|x|倍)")
# 可追溯线索：标签、源码位置、命令、脚本、文件名
TRACE_RE = re.compile(
    r"(" + LABEL_ALT + r"|[\w./-]+\.(?:py|md|sql|json|ya?ml|proto|toml|sh|ts|go|rs|java)"
    r"|\$ |`[^`]+`|命令|脚本|实测|运行)"
)
# 代码块围栏
FENCE_RE = re.compile(r"^\s*```")
# 输出行中已带标记
OUTPUT_MARK_RE = re.compile(r"\[(固定|随环境/版本变化)\]")


@dataclass
class Finding:
    file: str
    line: int
    level: str  # error | warning
    kind: str
    message: str
    text: str


def iter_markdown(targets: list[Path]):
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    for target in targets:
        if target.is_dir():
            for path in sorted(target.rglob("*.md")):
                if any(part in skip_dirs for part in path.parts):
                    continue
                yield path
        elif target.suffix == ".md":
            yield target


def check_placeholder(path: Path, lines: list[str]) -> list[Finding]:
    findings = []
    in_fence = False
    fence_open = 0
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if in_fence:
                fence_open = i
            continue
        if in_fence:
            continue
        if PLACEHOLDER_RE.match(line):
            findings.append(
                Finding(
                    str(path),
                    i,
                    "error",
                    "placeholder",
                    "残留模板占位段落；不适用内容应写「不适用」并给理由",
                    line.strip()[:80],
                )
            )
    return findings


def check_labels(path: Path, lines: list[str]) -> list[Finding]:
    """报告词表外标签。用于讨论/收敛旧标签的句子不算使用，跳过。"""
    findings = []
    reconciliation_hint = re.compile(r"收敛|统一到|词表|旧标签|例如|如下|等说法|不再")
    for i, line in enumerate(lines, 1):
        if reconciliation_hint.search(line):
            continue
        for legacy in LEGACY_LABELS:
            if legacy in line:
                findings.append(
                    Finding(
                        str(path),
                        i,
                        "warning",
                        "legacy-label",
                        f"使用了词表外标签「{legacy}」，应收敛到统一词表（如「未验证」）",
                        line.strip()[:80],
                    )
                )
    return findings


def check_numbers(path: Path, lines: list[str]) -> list[Finding]:
    findings = []
    in_fence = False
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "/.codex/" in line or line.lstrip().startswith("*"):
            continue
        for match in NUMBER_RE.finditer(line):
            window = "\n".join(lines[max(0, i - 3) : i])
            if TRACE_RE.search(window) or TRACE_RE.search(line):
                continue
            findings.append(
                Finding(
                    str(path),
                    i,
                    "warning",
                    "untraceable-number",
                    f"数字「{match.group(0).strip()}」附近缺少来源标签、命令或文件位置",
                    line.strip()[:80],
                )
            )
            break  # 每行只报一次，避免噪音
    return findings


def check_output_marks(path: Path, lines: list[str]) -> list[Finding]:
    """代码块中显式的输出行（如 `# 输出:`、`输出：`）必须带 [固定] / [随环境/版本变化] 标记。

    只认显式输出行，避免把含「输出」字样的说明句误判为输出。
    """
    findings = []
    in_fence = False
    output_line_re = re.compile(r"^\s*(#+\s*)?(输出|结果|output|Output|耗时)\s*[:：]")
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        if not output_line_re.search(line):
            continue
        if OUTPUT_MARK_RE.search(line):
            continue
        findings.append(
            Finding(
                str(path),
                i,
                "warning",
                "unmarked-output",
                "代码块中的输出未标注 [固定] 或 [随环境/版本变化]",
                line.strip()[:80],
            )
        )
    return findings


CHECKS = {
    "placeholder": check_placeholder,
    "legacy-label": check_labels,
    "untraceable-number": check_numbers,
    "unmarked-output": check_output_marks,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="技术文档质量门校验")
    parser.add_argument("targets", nargs="+", help="要检查的文件或目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(CHECKS),
        help="只运行指定检查，可重复",
    )
    args = parser.parse_args()

    targets = [Path(t) for t in args.targets]
    missing = [str(t) for t in targets if not t.exists()]
    if missing:
        print(f"路径不存在: {', '.join(missing)}", file=sys.stderr)
        return 1

    selected = args.only or sorted(CHECKS)
    findings: list[Finding] = []
    files_checked = 0

    for path in iter_markdown(targets):
        files_checked += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for name in selected:
            findings.extend(CHECKS[name](path, lines))

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    if args.json:
        print(
            json.dumps(
                {
                    "files_checked": files_checked,
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "findings": [asdict(f) for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for f in findings:
            mark = "ERROR" if f.level == "error" else "WARN "
            print(f"{mark} {f.file}:{f.line} [{f.kind}] {f.message}")
            print(f"      > {f.text}")
        print(
            f"\n检查 {files_checked} 个文件：{len(errors)} 个 error，{len(warnings)} 个 warning"
        )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
