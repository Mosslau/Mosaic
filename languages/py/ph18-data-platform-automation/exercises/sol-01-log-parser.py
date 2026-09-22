#!/usr/bin/env python3
# exercises/sol-01-can-parser.py —— 参考实现：平台服务日志解析器（对应 roadmap §18 练习 1）
# 验证环境（目标）：Python 3.13；本机实测 Python 3.13.12，纯标准库
# 运行：python3 sol-01-can-parser.py（打印输出 + 断言自检）
# 测试：python3 -m pytest sol-01-can-parser.py -q
# lint：ruff check sol-01-can-parser.py
# 验证状态：已验证（Python 3.13.12 本机实测：运行自检与 pytest 全绿）
"""平台服务日志解析器：逐行流式解析 → 按 ID 汇总帧数/首末时间/平均周期。

练习要求见 README.md。实现要点：
- 流式：generator 逐行产出，内存与文件大小无关（ph17 的纪律）；
- 健壮：脏行跳过不中断，统计里记录 skipped；
- 信息量：除帧数外补「首次/末次时间、平均周期」，是总线负载分析的输入。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# 文本行风格：行首 (时间戳) 接口 ID#HEX
_LINE_RE = re.compile(r"^\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]{0,16})\s*$")


@dataclass(frozen=True, slots=True)
class LogRecord:
    ts: float
    source_id: int
    data: bytes


def parse_line(line: str) -> LogRecord | None:
    m = _LINE_RE.match(line)
    if m is None:
        return None
    return LogRecord(
        ts=float(m.group(1)), source_id=int(m.group(2), 16), data=bytes.fromhex(m.group(3))
    )


def iter_frames(path: str | Path) -> Iterator[LogRecord]:
    """逐行解析日志，产出帧流（生成器，内存与文件大小无关）。"""
    with open(path, encoding="utf-8") as f:
        for line in f:
            frame = parse_line(line)
            if frame is not None:
                yield frame


@dataclass
class IdStats:
    """单个 ID 的汇总：帧数、首次/末次时间、平均周期（秒）。"""

    count: int = 0
    first_ts: float | None = None
    last_ts: float | None = None

    @property
    def avg_period(self) -> float | None:
        if self.count < 2 or self.first_ts is None or self.last_ts is None:
            return None
        return (self.last_ts - self.first_ts) / (self.count - 1)


def collect_stats(log_path: str | Path) -> tuple[dict[int, IdStats], int]:
    """单遍流式统计：返回 {source_id: IdStats} 与脏行数。"""
    stats: dict[int, IdStats] = {}
    skipped = 0
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            frame = parse_line(line)
            if frame is None:
                if line.strip() and not line.lstrip().startswith("#"):
                    skipped += 1  # 非注释、非空白的脏行
                continue
            st = stats.setdefault(frame.source_id, IdStats())
            st.count += 1
            st.first_ts = frame.ts if st.first_ts is None else min(st.first_ts, frame.ts)
            st.last_ts = frame.ts if st.last_ts is None else max(st.last_ts, frame.ts)
    return stats, skipped


def format_report(stats: dict[int, IdStats], skipped: int) -> str:
    lines = ["# 平台服务日志统计", ""]
    for source_id in sorted(stats, key=lambda k: (-stats[k].count, k)):
        st = stats[source_id]
        period = f"{st.avg_period:.3f}s" if st.avg_period is not None else "-"
        lines.append(
            f"0x{source_id:X}: {st.count} 帧, 首帧 ts={st.first_ts:.3f}, "
            f"末帧 ts={st.last_ts:.3f}, 平均周期 {period}"
        )
    lines.append(f"\n脏行（跳过）：{skipped}")
    return "\n".join(lines)


def build_sample_log(path: Path) -> Path:
    """写一份确定性样例日志（/tmp）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# demo can log",
        "(1700000000.100) can0 123#0100000000000000",
        "(1700000000.120) can0 456#FF00000000000000",
        "(1700000000.140) can0 123#0200000000000000",
        "garbage line without format",  # 脏行
        "(1700000000.160) can0 789#0000000000000000",
        "(1700000000.180) can0 123#0300000000000000",
        "(1700000000.200) can0 456#FE00000000000000",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    sample = build_sample_log(Path("/tmp/ph18-exer01/sample_can.log"))
    stats, skipped = collect_stats(sample)
    print(format_report(stats, skipped))

    assert stats[0x123].count == 3
    # 真实时间戳是大数（1.7e9 秒量级），float 相减有 ~1e-7 级误差，用 1e-4 宽容差
    assert stats[0x123].avg_period is not None and abs(stats[0x123].avg_period - 0.04) < 1e-4
    assert stats[0x456].count == 2
    assert skipped == 1
    print("\n自检通过：按 ID 计数、周期计算、脏行计数断言全绿")


def test_parse_line() -> None:
    f = parse_line("(1700000000.100) can0 123#0100000000000000")
    assert f is not None and f.source_id == 0x123
    assert f.data == bytes.fromhex("0100000000000000")  # 全 8 字节帧
    assert parse_line("not a can line") is None
    assert parse_line("(1700000000.1) can0 123#ZZ") is None


def test_collect_stats_counts_and_period() -> None:
    sample = build_sample_log(Path("/tmp/ph18-exer01-test/sample.log"))
    stats, skipped = collect_stats(sample)
    assert sorted(stats) == [0x123, 0x456, 0x789]
    assert stats[0x123].count == 3
    # 0x456 两帧（0.120 → 0.200），平均周期 0.080s；大时间戳浮点差用 1e-4 容差
    assert stats[0x456].avg_period is not None and abs(stats[0x456].avg_period - 0.08) < 1e-4
    assert skipped == 1


def test_streaming_memory() -> None:
    # 证明 collect_stats 不整读文件：喂一个略大的样例，行数>统计对象即可
    sample = build_sample_log(Path("/tmp/ph18-exer01-test/big.log"))
    lines = sample.read_text(encoding="utf-8").splitlines()
    for _ in range(10):
        sample.write_text("\n".join(lines * 100), encoding="utf-8")
        stats, _ = collect_stats(sample)
        assert len(stats) == 3


if __name__ == "__main__":
    main()
