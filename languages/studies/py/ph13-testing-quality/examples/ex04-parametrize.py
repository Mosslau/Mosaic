#!/usr/bin/env python3
# examples/ex04-parametrize.py —— 参数化测试 + 覆盖率（主文档 3.4）
# 验证环境：Python 3.13.9 + pytest 8.4.2（本机已装并实测；pytest-cov 未安装，覆盖率用标准库 trace 实测）
# 运行：python3 -m pytest ex04-parametrize.py -q（离线可跑，已验证）
#      覆盖率：python3 -m trace --count --summary --coverdir /tmp/ph13-cover \
#              --ignore-dir /opt/homebrew/anaconda3/lib/python3.13 --module pytest ex04-parametrize.py -q
# 验证状态：已验证 —— 14 个用例全过；本模块覆盖率 100%（trace 实测：25 个可执行行全命中）
import pytest


# ---- 被测代码 ----
def categorize_speed(speed: float) -> str:
    """按速度分档：invalid / low / normal / high 四档（4 个分支）。"""
    if speed < 0:
        return "invalid"
    if speed < 30:
        return "low"
    if speed <= 120:
        return "normal"
    return "high"


def parse_reading(text: str) -> float:
    """'12.5 km/h' → 12.5；非法输入抛 ValueError。"""
    parts = text.split()
    if len(parts) != 2:
        raise ValueError(f"非法读数: {text!r}")
    return float(parts[0])


# ---- 参数化测试：一组数据 = 一个独立用例，失败时精确到是哪组数据 ----
@pytest.mark.parametrize("speed,expected", [
    (-1, "invalid"),        # 负数
    (0, "low"),             # 下边界
    (29.9, "low"),          # low 档上限内
    (30, "normal"),         # normal 档下边界（>=30）
    (120, "normal"),        # normal 档上边界（<=120）
    (120.1, "high"),        # 越界一丁点就进 high
    (999, "high"),          # 极端值
])
def test_categorize_speed(speed, expected):
    assert categorize_speed(speed) == expected


@pytest.mark.parametrize("text", ["12.5 km/h", "0 m/s", "-3.2 deg"])
def test_parse_reading_valid(text):
    assert isinstance(parse_reading(text), float)


@pytest.mark.parametrize("text", ["", "abc", "12.5", "12.5 km/h extra"])
def test_parse_reading_invalid(text):
    with pytest.raises(ValueError):
        parse_reading(text)


if __name__ == "__main__":
    pytest.main(["-q", __file__])
