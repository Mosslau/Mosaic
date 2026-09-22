#!/usr/bin/env python3
# examples/ex01-can-dbc-parse.py —— CAN 日志解析 + DBC 信号解码 + 按 ID 流式统计（主文档 3.1）
# 验证环境：Python 3.13（本机实测 Python 3.13.12），依赖：纯标准库
# 运行：python3 ex01-can-dbc-parse.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex01-can-dbc-parse.py -q（收集 test_* 跑断言）
# lint：ruff check ex01-can-dbc-parse.py
# 验证状态：已验证（Python 3.13.12 本机实测：python3 自检与 python3 -m pytest 全绿）
"""CAN 日志按 ID 流式统计 + 极简 DBC 子集解析与信号解码。

ph17 project/ 的 streamlog（逐行生成器管线）在这里原样升级：行解析器换成 CAN
帧格式、过滤条件换成报文 ID、记录换成 (can_id, data)。本示例是 ph18 数据平台的
第一环 —— 后续 ex02~ex08 的遥测/电池/报表/服务都建立在这类「原始到结构化」的入口上。
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# 常见 CAN 日志行（candump 默认格式）：
#   (1685527200.123456) can0 123#AABBCCDD11223344
#   时间戳 | 接口 | 11/29 位 ID(hex) + # + 最多 8 字节数据(hex)
_LOG_RE = re.compile(r"^\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]{0,16})$")


@dataclass(frozen=True, slots=True)
class CanFrame:
    """一条 CAN 帧：时间戳(s) + 报文 ID + 原始数据字节。"""

    ts: float
    can_id: int
    data: bytes


def parse_can_line(line: str) -> CanFrame | None:
    """解析一行 CAN 日志；非帧行（空行/注释）返回 None，不抛异常。"""
    match = _LOG_RE.match(line.strip())
    if match is None:
        return None
    ts_raw, id_raw, data_hex = match.groups()
    return CanFrame(
        ts=float(ts_raw),
        can_id=int(id_raw, 16),
        data=bytes.fromhex(data_hex),
    )


@dataclass(frozen=True, slots=True)
class Signal:
    """DBC 信号定义（教学子集）：id/长度/字节序/符号/因子/偏移。

    解码公式：physical = raw * factor + offset。字节序约定见 decode()。
    """

    name: str
    start_bit: int
    length: int
    little_endian: bool  # DBC 的 0=Intel(小端), 1=Motorola(大端)
    is_signed: bool
    factor: float
    offset: float

    def decode(self, data: bytes) -> float | None:
        """从帧数据字节中解出信号原始值并换算物理量。

        支持两种布局：
        - Intel：start_bit 是全局 LSB-first 位号（byte*8+bit），信号位向上连续延伸；
        - Motorola：仅支持**字节对齐**信号（length % 8 == 0 且 start_bit % 8 == 7），
          信号以字节序连续摆放。任意位级 Motorola 位序换算较复杂，属 cantools 等
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
        # 字节对齐假设：高字节排最前（大端）。DBC 位号换算后高字节落在
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
class Message:
    """一个 CAN 报文（DBC 的 BO_）：含名称与若干信号。"""

    can_id: int
    name: str
    dlc: int
    signals: list[Signal] = field(default_factory=list)


_BO_RE = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)")
_SG_RE = re.compile(
    r"^SG_\s+(\w+)\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*"
    r"\(([-\d.eE]+),([-\d.eE]+)\)\s*\[([-\d.|]+)\]\s*\"([^\"]*)\""
)


def parse_dbc(text: str) -> dict[int, Message]:
    """解析 DBC 教学子集：只认 BO_ 与紧随其后的 SG_，其余行（VERSION/NS_/BU_/CM_/VAL_）跳过。

    SG_ 行语法：SG_ 名 : 起始位|长度@字节序 符号 (因子,偏移) [min|max] "单位" 接收节点
    """
    messages: dict[int, Message] = {}
    current: Message | None = None
    for raw in text.splitlines():
        line = raw.strip()
        bo = _BO_RE.match(line)
        if bo is not None:
            current = Message(can_id=int(bo.group(1)), name=bo.group(2), dlc=int(bo.group(3)))
            messages[current.can_id] = current
            continue
        sg = _SG_RE.match(line)
        if sg is not None and current is not None:
            # 组 3 是信号名；组 4 起：起始位|长度@字节序(0=Intel/1=Motorola) 符号(+/-)
            # 组 7/8 为因子与偏移；组 9 为 min|max（本子集不解析，仅匹配跳过）
            current.signals.append(
                Signal(
                    name=sg.group(1),
                    start_bit=int(sg.group(2)),
                    length=int(sg.group(3)),
                    little_endian=sg.group(4) == "0",
                    is_signed=sg.group(5) == "-",
                    factor=float(sg.group(6)),
                    offset=float(sg.group(7)),
                )
            )
    return messages


def iter_frames(log_path: str | Path) -> Iterator[CanFrame]:
    """逐行产出 CAN 帧（生成器，内存与文件大小无关 —— ph17 的流式纪律在此延续）。"""
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            frame = parse_can_line(line)
            if frame is not None:
                yield frame


def stats_by_id(log_path: str | Path) -> Counter[int]:
    """按报文 ID 统计帧数：只遍历一次，逐帧累加。"""
    counter: Counter[int] = Counter()
    for frame in iter_frames(log_path):
        counter[frame.can_id] += 1
    return counter


# ---- 内嵌样例数据：真实车联网日志与 DBC 的「缩小版」，教学专用 ----
# 说明：CAN 日志里 ID 是十六进制（candump 惯例），DBC 里 BO_ 编号是十进制。
# 下列 DBC 十进制编号恰好对应日志里的 hex ID：123→0x7B、291→0x123、312→0x138、400→0x190
_SAMPLE_LOG = """# ph18 ex01 教学样例日志（candump 格式，多车总线取单车片段）
(1700000000.100000) can0 7B#C800000000000000
(1700000000.101000) can0 123#A500000000000000
(1700000000.102000) can0 138#E80C000000000000
(1700000000.103000) can0 190#5802000000000000
(1700000000.200000) can0 7B#C800000000000000
(1700000000.201000) can0 123#A400000000000000
(1700000000.202000) can0 138#E810000000000000
(1700000000.203000) can0 190#5802010000000000
# 文件尾部留一个注释行，用于验证 parse_can_line 对非帧行的容忍
"""

_SAMPLE_DBC = """VERSION "demo"
NS_ :
BU_ : Vector__XXX
BO_ 123 PowerStatus: 8 Vector__XXX
 SG_ SocPercent : 0|8@0+ (0.4,0) [0|100] "%" Vector__XXX
BO_ 291 BatteryVoltage: 8 Vector__XXX
 SG_ BatteryVoltage : 7|8@1+ (0.1,0) [0|40] "V" Vector__XXX
BO_ 312 MotorStatus: 8 Vector__XXX
 SG_ MotorRpm : 23|16@1+ (0.25,0) [0|16000] "rpm" Vector__XXX
 SG_ MotorTorque : 7|8@1- (1,0) [-128|127] "Nm" Vector__XXX
BO_ 400 VehicleSpeed: 8 Vector__XXX
 SG_ VehicleSpeed : 0|16@0+ (0.01,0) [0|650] "km/h" Vector__XXX
 SG_ VehicleGear : 16|4@0+ (1,0) [0|15] "" Vector__XXX
"""


def build_sample_files() -> tuple[Path, Path]:
    """把样例日志与 DBC 写到 /tmp（产物纪律：不在仓库残留数据文件）。"""
    tmp = Path("/tmp/ph18-ex01")
    tmp.mkdir(parents=True, exist_ok=True)
    log_path = tmp / "sample_can.log"
    dbc_path = tmp / "vehicle.dbc"
    log_path.write_text(_SAMPLE_LOG, encoding="utf-8")
    dbc_path.write_text(_SAMPLE_DBC, encoding="utf-8")
    return log_path, dbc_path


def main() -> None:
    log_path, dbc_path = build_sample_files()
    messages = parse_dbc(dbc_path.read_text(encoding="utf-8"))
    print("== DBC 解析结果 ==")
    for msg in messages.values():
        sigs = ", ".join(f"{s.name}({s.length}bit)" for s in msg.signals)
        print(f"  0x{msg.can_id:X} {msg.name}: {sigs}")

    print("\n== 按 ID 流式统计（帧数）==")
    for can_id, count in stats_by_id(log_path).most_common():
        print(f"  0x{can_id:X} → {count} 帧")

    print("\n== 信号解码样例 ==")
    for frame in iter_frames(log_path):
        msg = messages.get(frame.can_id)
        if msg is None or not msg.signals:
            continue
        decoded: dict[str, float] = {}
        for sig in msg.signals:
            value = sig.decode(frame.data)
            # 0.1/0.4 这类十进制因子乘出来会有浮点尾数（如 16.400000000000002），展示时保留 2 位
            if value is not None:
                decoded[sig.name] = round(value, 2)
        print(f"  0x{frame.can_id:X} {msg.name}: {decoded}")

    # ---- 自检断言 ----
    for can_id in (0x7B, 0x123, 0x138, 0x190):
        assert stats_by_id(log_path)[can_id] == 2
    frames = list(iter_frames(log_path))
    assert len(frames) == 8  # 注释行不计入
    assert frames[0].data == bytes.fromhex("C800000000000000")
    # VehicleSpeed(0x190) 的 VehicleSpeed 信号（Intel 16bit @0）：0x58 0x02 小端 raw=600 → 6.0 km/h
    speed_msg = messages[0x190]
    assert speed_msg.signals[0].decode(bytes.fromhex("5802")) == 6.0
    # MotorRpm(MotorStatus, Motorola 16bit @23)：高字节在 wire 字节 1
    rpm_sig = messages[0x138].signals[0]
    # 两字节数据 0x10 0x00：raw = 0x1000 = 4096 → 4096*0.25 = 1024 rpm
    assert rpm_sig.decode(b"\x00\x10\x00\x00\x00\x00\x00\x00") == 1024.0
    print("\n自检通过：帧统计、DBC 解析、信号解码断言全绿")


def test_parse_can_line() -> None:
    frame = parse_can_line("(1700000000.100000) can0 123#7D00000000000000")
    assert frame is not None and frame.can_id == 0x123
    assert frame.data == bytes.fromhex("7D00000000000000")


def test_parse_can_line_ignores_junk() -> None:
    assert parse_can_line("") is None
    assert parse_can_line("# 注释行") is None
    assert parse_can_line("(1700000000.1) can0 123#GG") is None  # 非法 hex


def test_iter_frames_is_streaming() -> None:
    log_path, _ = build_sample_files()
    assert sum(1 for _ in iter_frames(log_path)) == 8  # 注释行不计入


def test_decode_intel_16bit() -> None:
    # DBC 的 BO_ 编号是十进制：400 → 0x190
    msg = parse_dbc('BO_ 400 V: 8 X\n SG_ S : 0|16@0+ (0.01,0) [0|650] "km/h" X')[0x190]
    # 数据 0x58 0x02：Intel 小端 raw = 0x0258 = 600 → 6.0 km/h
    assert msg.signals[0].decode(bytes.fromhex("5802")) == 6.0


def test_decode_motorola_16bit() -> None:
    # DBC 的 BO_ 编号是十进制：312 → 0x138；需给足 8 字节帧长
    msg = parse_dbc('BO_ 312 M: 8 X\n SG_ Rpm : 23|16@1+ (0.25,0) [0|16000] "rpm" X')[0x138]
    assert msg.signals[0].decode(bytes.fromhex("0010000000000000")) == 1024.0
    assert msg.signals[0].decode(bytes.fromhex("0010400000000000")) == 1040.0


if __name__ == "__main__":
    main()
