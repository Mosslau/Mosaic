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
    python3 check_doc_quality.py --allow-pending algorithms/ engineering/

骨架文档:
    以「状态：⬜ 未开始 / 待实现 / 骨架」标记的文档视为骨架文档，其模板占位
    是合法的待办标记。加 --allow-pending 时，骨架文档中的占位降为 warning 并
    计入统计；未加该参数时仍按 error 报告（严格模式，默认）。
    标记为「已完成 / 理论文档」或没有状态行的文档不属于骨架文档，其占位始终
    是 error —— 占位本身不是问题，占位出现在声称已完成的文档里才是问题。

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
    "来源确认",
    "文档确认",
    "设计意图",
    "未验证",
]
LABEL_ALT = "|".join(FACT_LABELS)

# 词表外的旧标签：仅在「标签位」出现时报告（见 check_labels）
LEGACY_LABELS = [
    "生产验证",
    "测试环境验证",
    "迁移文件确认",
    "ORM 确认",
    "契约文件确认",
]

# 说明性标记：括号内容在解释「这份文档/这条注释」自身，而不是向作者提问
NOTE_MARKERS = re.compile(
    r"本文件|本文|本目录|本 skill|契约|reference|规范建议|调用方|"
    r"不适用|未验证|未实测|来源确认|源码确认|运行确认|规范确认|设计意图|"
    r"见 |参见|详见|即 |等价于"
)

# 「不适用」是允许的通过结果
NOT_APPLICABLE = "不适用"

# 以全角/半角括号开头的整段：真占位是「裸提示」，说明性括号不算
PLACEHOLDER_RE = re.compile(r"^\s*[（(]([^）)]{6,})[）)]\s*$")
_LABEL_PREFIX_RE = re.compile(r"^(来源|源码|运行|规范|文档|设计|未验证)")

# 骨架文档标记：状态行声明未开始/待实现/骨架时，其模板占位是合法待办
PENDING_MARKER_RE = re.compile(r"未开始|待实现|骨架|TODO\s*[:：]\s*待|⬜")

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


def is_pending_doc(lines: list[str]) -> bool:
    """状态行声明未开始/待实现/骨架的文档，其模板占位是合法待办标记。

    只检查文档开头 12 行，避免把正文里出现的「未开始」误判为文档状态。
    """
    return any(PENDING_MARKER_RE.search(line) for line in lines[:12])


def _is_placeholder(line: str) -> bool:
    """判断整段括号是否为模板占位提示句。

    真占位是「裸提示」——直接向作者提问或命令作者做什么，例如
    「（关键公式与推导过程，手推一遍再写代码）」。说明性括号在解释这条
    注释/这份文档自身（含「本文件/不适用/来源确认/见 …」等标记），不算占位。
    """
    match = PLACEHOLDER_RE.match(line)
    if not match:
        return False
    body = match.group(1)
    if NOTE_MARKERS.search(body) or _LABEL_PREFIX_RE.match(body):
        return False
    return True


def check_placeholder(
    path: Path, lines: list[str], allow_pending: bool = False
) -> list[Finding]:
    findings: list[Finding] = []
    pending = is_pending_doc(lines)
    # 骨架文档 + 显式放行：占位降为 warning；否则始终是 error
    level = "warning" if (pending and allow_pending) else "error"
    message = (
        "骨架文档的待办占位（已由 --allow-pending 放行）"
        if level == "warning"
        else "残留模板占位段落；不适用内容应写「不适用」并给理由"
    )
    in_fence = False
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _is_placeholder(line):
            findings.append(
                Finding(
                    str(path),
                    i,
                    level,
                    "placeholder",
                    message,
                    line.strip()[:80],
                )
            )
    return findings


def check_labels(path: Path, lines: list[str]) -> list[Finding]:
    """报告处于「标签位」的词表外旧标签。

    只在旧标签被当作标签使用时报错，即位于反引号内、句末、斜杠分隔的并列标签中，
    或答案行的行首。这样既不会误报讨论旧标签的句子，也不会误报
    「在测试环境验证过」这类自然叙述——而后者正是上一轮的误报来源。
    """
    findings = []
    reconciliation_hint = re.compile(r"收敛|统一到|词表|旧标签|例如|如下|等说法|不再")
    for i, line in enumerate(lines, 1):
        if reconciliation_hint.search(line):
            continue
        for legacy in LEGACY_LABELS:
            if legacy not in line:
                continue
            if not _is_label_position(line, legacy):
                continue
            findings.append(
                Finding(
                    str(path),
                    i,
                    "warning",
                    "legacy-label",
                    f"使用了词表外标签「{legacy}」，应收敛到统一词表（如「来源确认」或「未验证」）",
                    line.strip()[:80],
                )
            )
    return findings


def _is_label_position(line: str, label: str) -> bool:
    """判断 label 是否处在「标签位」而非自然语句中。"""
    escaped = re.escape(label)
    patterns = [
        rf"`{escaped}`",  # 反引号包裹
        rf"{escaped}\s*[）)]\s*$",  # 句末括号收口
        rf"{escaped}\s*$",  # 直接句末
        rf"{escaped}\s*[、／/|]\s*(?:{LABEL_ALT})",  # 并列标签
        rf"(?:{LABEL_ALT})\s*[、／/|]\s*{escaped}",  # 并列标签（另一侧）
        rf"^\s*(?:[-*>]\s*)?{escaped}\s*[:：]",  # 列表项/表格单元格的行首标签
        rf"\|\s*{escaped}\s*\|",  # 表格单元格
    ]
    return any(re.search(p, line) for p in patterns)


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


def make_placeholder_check(allow_pending: bool):
    """生成绑定 allow_pending 的占位检查，使各检查可统一调用。"""

    def run(path: Path, lines: list[str]) -> list[Finding]:
        return check_placeholder(path, lines, allow_pending=allow_pending)

    return run


def build_checks(allow_pending: bool) -> dict:
    return {
        "placeholder": make_placeholder_check(allow_pending),
        "legacy-label": check_labels,
        "untraceable-number": check_numbers,
        "unmarked-output": check_output_marks,
    }


CHECK_NAMES = [
    "placeholder",
    "legacy-label",
    "untraceable-number",
    "unmarked-output",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="技术文档质量门校验")
    parser.add_argument("targets", nargs="+", help="要检查的文件或目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="骨架文档（状态：⬜ 未开始/待实现/骨架）的待办占位降为 warning",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=CHECK_NAMES,
        help="只运行指定检查，可重复",
    )
    args = parser.parse_args()

    targets = [Path(t) for t in args.targets]
    missing = [str(t) for t in targets if not t.exists()]
    if missing:
        print(f"路径不存在: {', '.join(missing)}", file=sys.stderr)
        return 1

    checks = build_checks(args.allow_pending)
    selected = args.only or CHECK_NAMES
    findings: list[Finding] = []
    files_checked = 0
    pending_files = 0

    for path in iter_markdown(targets):
        files_checked += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        if is_pending_doc(lines):
            pending_files += 1
        for name in selected:
            findings.extend(checks[name](path, lines))

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]
    pending_placeholders = [f for f in warnings if f.kind == "placeholder"]

    if args.json:
        print(
            json.dumps(
                {
                    "files_checked": files_checked,
                    "pending_files": pending_files,
                    "allow_pending": args.allow_pending,
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "pending_placeholders": len(pending_placeholders),
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
        if pending_files:
            if args.allow_pending:
                print(
                    f"其中骨架文档 {pending_files} 个，已放行 {len(pending_placeholders)} 处待办占位"
                )
            else:
                print(
                    f"其中骨架文档 {pending_files} 个，其待办占位按严格模式计为 error；"
                    f"如属合法待办可加 --allow-pending"
                )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
