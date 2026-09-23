#!/usr/bin/env python3
# exercises/sol-04-parametrize-coverage.py —— 练习 4 参考实现：参数化测试 + 覆盖率（数据处理测试）
# 验证环境：Python 3.13.9 + pytest 8.4.2（stdlib 实现；pytest-cov 未装，覆盖率用标准库 trace 实测）
# 运行：python3 -m pytest sol-04-parametrize-coverage.py -q（离线可跑，已验证）
#      覆盖率：python3 -m trace --count --summary --coverdir /tmp/ph13-sol-cover
#              --ignore-dir <site-packages> --module pytest sol-04-parametrize-coverage.py -q
# 验证状态：已验证 —— 18 个用例全过；本文件语句覆盖率 100%（trace 实测：36 个可执行行全命中）
# 验证块数字实测：python3 -m pytest sol-04-parametrize-coverage.py -q -> 18 passed
#                trace 覆盖率 -> lines 36, cov 100%
import pytest


# ---- 被测代码（设备遥测数据处理）----
def categorize_speed(speed: float) -> str:
    """速度分档：invalid / low / normal / high（4 个分支都要有测试覆盖）。"""
    if speed < 0:
        return "invalid"
    if speed < 30:
        return "low"
    if speed <= 120:
        return "normal"
    return "high"


def parse_reading(text: str) -> float:
    """'42.5 km/h' → 42.5；格式非法抛 ValueError。"""
    parts = text.split()
    if len(parts) != 2:
        raise ValueError(f"非法读数: {text!r}")
    return float(parts[0])


def estimate_range(component_kwh: float, consumption: float) -> float:
    """续航估算 = 电量 / 百公里能耗 × 100；能耗为 0 视为参数错误。"""
    if consumption <= 0:
        raise ValueError("能耗必须为正数")
    return round(component_kwh / consumption * 100, 1)


# ---- 参数化测试 ----
@pytest.mark.parametrize("speed,expected", [
    (-1, "invalid"),        # 负数
    (0, "low"),             # low 下边界
    (29.9, "low"),
    (30, "normal"),         # normal 下边界（>=30）
    (120, "normal"),        # normal 上边界（<=120）
    (120.1, "high"),        # 越界即 high
    (999, "high"),
], ids=["neg", "low0", "low29", "norm30", "norm120", "high120.1", "high999"])
def test_categorize_speed(speed, expected):
    assert categorize_speed(speed) == expected


@pytest.mark.parametrize("text", ["12.5 km/h", "0 m/s", "-3.2 deg"])
def test_parse_reading_valid(text):
    assert isinstance(parse_reading(text), float)


@pytest.mark.parametrize("text", ["", "abc", "12.5", "12.5 km/h extra"])
def test_parse_reading_invalid(text):
    with pytest.raises(ValueError):
        parse_reading(text)


@pytest.mark.parametrize("component,consumption,expected", [
    (60.0, 12.5, 480.0),
    (40.0, 20.0, 200.0),
    (80.0, 15.0, 533.3),
])
def test_estimate_range(component, consumption, expected):
    assert estimate_range(component, consumption) == expected


def test_estimate_range_zero_consumption():
    with pytest.raises(ValueError):
        estimate_range(60.0, 0)


if __name__ == "__main__":
    pytest.main(["-q", __file__])
