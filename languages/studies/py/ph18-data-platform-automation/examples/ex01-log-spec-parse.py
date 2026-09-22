#!/usr/bin/env python3
# examples/ex01-log-spec-parse.py —— 平台日志解析 + 格式规约解码 + 按来源统计（主文档 3.1）
# 验证环境：Python 3.13（本机实测 Python 3.13.9），依赖：纯标准库
# 运行：python3 ex01-log-spec-parse.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex01-log-spec-parse.py -q（收集 test_* 跑断言）
# lint：ruff check ex01-log-spec-parse.py
# 验证状态：已验证（Python 3.13.9 本机实测：python3 自检与 python3 -m pytest 全绿）
"""平台服务日志按来源流式统计 + 极简格式规约子集解析与字段解码。

ph17 project/ 的 streamlog（逐行生成器管线）在这里原样升级：行解析器换成平台
**日志行格式**、过滤条件换成日志来源 ID、记录换成 (source_id, data)。本示例是
ph18 数据平台分析的第一环 —— 后续 ex02~ex08 的指标清洗/资源健康度/报表/服务
都建立在这类「原始字节 → 结构化字段」的入口上。
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# 常见平台采集日志行格式（文本行协议，一行一条记录）：
#   (1685527200.123456) node0 123#AABBCCDD11223344
#   时间戳 | 采集节点 | 来源 ID(hex) + # + 最多 8 字节原始数据(hex)
_LOG_RE = re.compile(r"^\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]{0,16})$")


@dataclass(frozen=True, slots=True)
class LogRecord:
    """一条日志记录：时间戳(s) + 日志来源 ID + 原始数据字节。"""

    ts: float
    source_id: int
    data: bytes


def parse_log_line(line: str) -> LogRecord | None:
    """解析一行平台日志；非记录行（空行/注释）返回 None，不抛异常。"""
    match = _LOG_RE.match(line.strip())
    if match is None:
        return None
    ts_raw, id_raw, data_hex = match.groups()
    return LogRecord(
        ts=float(ts_raw),
        source_id=int(id_raw, 16),
        data=bytes.fromhex(data_hex),
    )


@dataclass(frozen=True, slots=True)
class Field:
    """格式规约的字段定义（教学子集）：id/长度/字节序/符号/因子/偏移。

    解码公式：physical = raw * factor + offset。字节序约定见 decode()。
    """

    name: str
    start_bit: int
    length: int
    little_endian: bool  # 规约的 0=小端(Intel), 1=大端(Motorola)
    is_signed: bool
    factor: float
    offset: float

    def decode(self, data: bytes) -> float | None:
        """从记录字节中解出字段原始值并换算为物理量。

        支持两种布局：
        - 小端：start_bit 是全局 LSB-first 位号（byte*8+bit），字段位向上连续延伸；
        - 大端：仅支持**字节对齐**字段（length % 8 == 0 且 start_bit % 8 == 7），
          字段以字节序连续摆放。任意位级大端位序换算较复杂，属 cantools/构造库等
          完整工具库范畴，教学子集不实现（主文档 4.1 有说明）。
        """
        if len(data) * 8 < self.start_bit + self.length:
            return None
        if self.little_endian:
            raw = self._decode_intel(data)
        else:
            raw = self._decode_motorola(data)
        return raw * self.factor + self.offset

    def _decode_intel(self, data: bytes) -> int:
        raw = 0
        for bit_offset in range(self.length):
            pos = self.start_bit + bit_offset  # LSB 在前，位号递增
            byte, bit = divmod(pos, 8)
            if data[byte] >> bit & 1:
                raw |= 1 << bit_offset
        return self._apply_sign(raw)

    def _decode_motorola(self, data: bytes) -> int:
        # 字节对齐假设：高字节排最前（大端）。规约位号换算后高字节落在
        # wire 索引 (start_bit + 1)//8 - length//8，见主文档 4.1 的推导。
        assert self.length % 8 == 0 and self.start_bit % 8 == 7
        n_bytes = self.length // 8
        msb_byte = (self.start_bit + 1) // 8 - n_bytes
        raw = int.from_bytes(data[msb_byte : msb_byte + n_bytes], "big")
        return self._apply_sign(raw)

    def _apply_sign(self, raw: int) -> int:
        if self.is_signed and raw & (1 << (self.length - 1)):
            raw -= 1 << self.length
        return raw


@dataclass
class RecordDef:
    """一条记录定义（规约的 REC 行）：含名称与若干字段。"""

    source_id: int
    name: str
    length: int
    fields: list[Field] = field(default_factory=list)


_REC_RE = re.compile(r"^REC\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)")
_FLD_RE = re.compile(
    r"^FLD\s+(\w+)\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*"
    r"\(([-\d.eE]+),([-\d.eE]+)\)\s*\[([-\d.|]+)\]\s*\"([^\"]*)\""
)


def parse_logspec(text: str) -> dict[int, RecordDef]:
    """解析格式规约教学子集：只认 REC 与紧随其后的 FLD，其余行（VERSION/NS_ 等）跳过。

    FLD 行语法：FLD 名 : 起始位|长度@字节序 符号 (因子,偏移) [min|max] "单位" 采集器
    """
    records: dict[int, RecordDef] = {}
    current: RecordDef | None = None
    for raw in text.splitlines():
        line = raw.strip()
        rec = _REC_RE.match(line)
        if rec is not None:
            current = RecordDef(
                source_id=int(rec.group(1)), name=rec.group(2), length=int(rec.group(3))
            )
            records[current.source_id] = current
            continue
        fld = _FLD_RE.match(line)
        if fld is not None and current is not None:
            # 组 3 是字段名；组 4 起：起始位|长度@字节序(0=小端/1=大端) 符号(+/-)
            # 组 7/8 为因子与偏移；组 9 为 min|max（本子集不解析，仅匹配跳过）
            current.fields.append(
                Field(
                    name=fld.group(1),
                    start_bit=int(fld.group(2)),
                    length=int(fld.group(3)),
                    little_endian=fld.group(4) == "0",
                    is_signed=fld.group(5) == "-",
                    factor=float(fld.group(6)),
                    offset=float(fld.group(7)),
                )
            )
    return records


def iter_records(log_path: str | Path) -> Iterator[LogRecord]:
    """逐行产出日志记录（生成器，内存与文件大小无关 —— ph17 的流式纪律在此延续）。"""
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            if record is not None:
                yield record


def stats_by_id(log_path: str | Path) -> Counter[int]:
    """按日志来源 ID 统计记录数：只遍历一次，逐条累加。"""
    counter: Counter[int] = Counter()
    for record in iter_records(log_path):
        counter[record.source_id] += 1
    return counter


# ---- 内嵌样例数据：真实采集日志与格式规约的「缩小版」，教学专用 ----
# 说明：日志行里来源 ID 是十六进制，规约里 REC 编号是十进制。
# 下列规约十进制编号恰好对应日志里的 hex ID：123→0x7B、291→0x123、312→0x138、400→0x190
_SAMPLE_LOG = """# ph18 ex01 教学样例日志（文本行格式，多采集节点取单节点片段）
(1700000000.100000) node0 7B#C800000000000000
(1700000000.101000) node0 123#A500000000000000
(1700000000.102000) node0 138#E80C000000000000
(1700000000.103000) node0 190#5802000000000000
(1700000000.200000) node0 7B#C800000000000000
(1700000000.201000) node0 123#A400000000000000
(1700000000.202000) node0 138#E810000000000000
(1700000000.203000) node0 190#5802010000000000
# 文件尾部留一个注释行，用于验证 parse_log_line 对非记录行的容忍
"""

_SAMPLE_SPEC = """VERSION "demo"
NS_ :
BU_ : collector__XXX
REC 123 CpuStatus: 8 collector__XXX
 FLD CpuPercent : 0|8@0+ (0.4,0) [0|100] "%" collector__XXX
REC 291 MemUsed: 8 collector__XXX
 FLD MemUsed : 7|8@1+ (0.1,0) [0|40] "GB" collector__XXX
REC 312 NetStatus: 8 collector__XXX
 FLD NetIops : 23|16@1+ (0.25,0) [0|16000] "io/s" collector__XXX
 FLD NetErrRate : 7|8@1- (1,0) [-128|127] "/min" collector__XXX
REC 400 ServiceLatency: 8 collector__XXX
 FLD LatencyMs : 0|16@0+ (0.01,0) [0|650] "ms" collector__XXX
 FLD StatusCode : 16|4@0+ (1,0) [0|15] "" collector__XXX
"""


def build_sample_files() -> tuple[Path, Path]:
    """把样例日志与格式规约写到 /tmp（产物纪律：不在仓库残留数据文件）。"""
    tmp = Path("/tmp/ph18-ex01")
    tmp.mkdir(parents=True, exist_ok=True)
    log_path = tmp / "sample_service.log"
    spec_path = tmp / "service.spec"
    log_path.write_text(_SAMPLE_LOG, encoding="utf-8")
    spec_path.write_text(_SAMPLE_SPEC, encoding="utf-8")
    return log_path, spec_path


def main() -> None:
    log_path, spec_path = build_sample_files()
    records = parse_logspec(spec_path.read_text(encoding="utf-8"))
    print("== 格式规约解析结果 ==")
    for rec in records.values():
        fields = ", ".join(f"{f.name}({f.length}bit)" for f in rec.fields)
        print(f"  0x{rec.source_id:X} {rec.name}: {fields}")

    print("\n== 按来源 ID 流式统计（记录数）==")
    for source_id, count in stats_by_id(log_path).most_common():
        print(f"  0x{source_id:X} → {count} 条")

    print("\n== 字段解码样例 ==")
    for record in iter_records(log_path):
        rec = records.get(record.source_id)
        if rec is None or not rec.fields:
            continue
        decoded: dict[str, float] = {}
        for fld in rec.fields:
            value = fld.decode(record.data)
            # 0.1/0.4 这类十进制因子乘出来会有浮点尾数（如 16.400000000000002），展示时保留 2 位
            if value is not None:
                decoded[fld.name] = round(value, 2)
        print(f"  0x{record.source_id:X} {rec.name}: {decoded}")

    # ---- 自检断言 ----
    for source_id in (0x7B, 0x123, 0x138, 0x190):
        assert stats_by_id(log_path)[source_id] == 2
    records_list = list(iter_records(log_path))
    assert len(records_list) == 8  # 注释行不计入
    assert records_list[0].data == bytes.fromhex("C800000000000000")
    # ServiceLatency(0x190) 的 LatencyMs 字段（小端 16bit @0）：0x58 0x02 小端 raw=600 → 6.0 ms
    latency_rec = records[0x190]
    assert latency_rec.fields[0].decode(bytes.fromhex("5802")) == 6.0
    # NetIops(NetStatus, 大端 16bit @23)：高字节在 wire 字节 1
    iops_fld = records[0x138].fields[0]
    # 两字节数据 0x10 0x00：raw = 0x1000 = 4096 → 4096*0.25 = 1024 io/s
    assert iops_fld.decode(b"\x00\x10\x00\x00\x00\x00\x00\x00") == 1024.0
    print("\n自检通过：记录统计、格式规约解析、字段解码断言全绿")


def test_parse_log_line() -> None:
    record = parse_log_line("(1700000000.100000) node0 123#7D00000000000000")
    assert record is not None and record.source_id == 0x123
    assert record.data == bytes.fromhex("7D00000000000000")


def test_parse_log_line_ignores_junk() -> None:
    assert parse_log_line("") is None
    assert parse_log_line("# 注释行") is None
    assert parse_log_line("(1700000000.1) node0 123#GG") is None  # 非法 hex


def test_iter_records_is_streaming() -> None:
    log_path, _ = build_sample_files()
    assert sum(1 for _ in iter_records(log_path)) == 8  # 注释行不计入


def test_decode_little_endian_16bit() -> None:
    # 规约的 REC 编号是十进制：400 → 0x190
    rec = parse_logspec('REC 400 V: 8 X\n FLD S : 0|16@0+ (0.01,0) [0|650] "ms" X')[0x190]
    # 数据 0x58 0x02：小端 raw = 0x0258 = 600 → 6.0 ms
    assert rec.fields[0].decode(bytes.fromhex("5802")) == 6.0


def test_decode_big_endian_16bit() -> None:
    # 规约的 REC 编号是十进制：312 → 0x138；需给足 8 字节长度
    rec = parse_logspec('REC 312 M: 8 X\n FLD Iops : 23|16@1+ (0.25,0) [0|16000] "io/s" X')[0x138]
    assert rec.fields[0].decode(bytes.fromhex("0010000000000000")) == 1024.0
    assert rec.fields[0].decode(bytes.fromhex("0010400000000000")) == 1040.0


if __name__ == "__main__":
    main()
