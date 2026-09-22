#!/usr/bin/env python3
# examples/ex05b-mypy-bugs.py —— 故意出错示例（类型错误版）：仅供 mypy 检查演示，请勿直接运行
# 验证环境：Python 3.13.9 + mypy 1.17.1（本机已装并实测）
# 运行：mypy ex05b-mypy-bugs.py（已验证：报 4 处错误，见下；故意写错，直接运行会抛 AttributeError）
# 验证状态：已验证 —— mypy 报告 4 个错误（assignment ×2 / attr-defined / arg-type；错误 1、2 的消息同为 "Incompatible types in assignment"）
from dataclasses import dataclass


@dataclass
class Vehicle:
    vehicle_id: str
    speed: float


def add(a: int, b: int) -> int:
    return a + b


def total_speed(vehicles: list[Vehicle]) -> int:
    total = 0
    for v in vehicles:
        total += v.speed            # 错误 2: assignment —— float 累加进 int 变量（与错误 1 同为 assignment 码）
    return total


def speed_label(v: Vehicle) -> str:
    return v.vehicle_id.upper()


def main() -> None:
    x: str = add(1, 2)              # 错误 1: assignment —— int 赋给声明为 str 的变量
    print(x)
    print(speed_label(Vehicle("EV-001", 42)))
    v = Vehicle("EV-002", 30.0)
    print(v.speed.upper())          # 错误 3: attr-defined —— float 没有 upper 方法
    total = total_speed([v])
    print(total, add("1", 2))       # 错误 4: arg-type —— str 传给声明为 int 的参数


if __name__ == "__main__":
    main()
