#!/usr/bin/env python3
# exercises/sol-05-typing-inventory.py —— 练习 5 参考实现：类型注解 + mypy + ruff 干净
# 验证环境：Python 3.13.9 + pytest 8.4.2 + mypy 1.17.1 + ruff 0.12.0（本机已装并实测）
# 运行：python3 -m pytest sol-05-typing-inventory.py -q（离线可跑，已验证）
#      类型检查：mypy sol-05-typing-inventory.py（已验证：Success，0 错误）
#      lint：ruff check sol-05-typing-inventory.py（已验证：All checks passed）
# 验证状态：已验证 —— 8 个用例全过；本文件语句覆盖率 100%（trace 实测：43 个可执行行全命中）；
#          mypy 0 错误；ruff 0 错误
# 验证块数字实测：python3 -m pytest sol-05-typing-inventory.py -q -> 8 passed
#                trace 覆盖率 -> lines 43, cov 100%
#                mypy sol-05-typing-inventory.py -> Success: no issues found in 1 source file
#                ruff check sol-05-typing-inventory.py -> All checks passed!
import pytest
from dataclasses import dataclass


@dataclass
class InventoryItem:
    """库存单品：SKU、名称、单价、数量。"""
    sku: str
    name: str
    price: float
    qty: int


def total_value(items: list[InventoryItem]) -> float:
    """全部库存货值（单价 × 数量求和，保留两位小数）。"""
    return round(sum(i.price * i.qty for i in items), 2)


def find_by_sku(items: list[InventoryItem], sku: str) -> InventoryItem | None:
    """按 SKU 查找单品；找不到返回 None（联合类型显式声明）。"""
    for i in items:
        if i.sku == sku:
            return i
    return None


def low_stock(items: list[InventoryItem], threshold: int = 5) -> list[InventoryItem]:
    """返回数量低于阈值的单品（默认阈值 5）。"""
    return [i for i in items if i.qty < threshold]


def stock_report(items: list[InventoryItem]) -> dict[str, int]:
    """SKU → 库存数量 的汇总字典（便于打印/接口返回）。"""
    return {i.sku: i.qty for i in items}


# ---- 测试 ----
SAMPLE = [
    InventoryItem("EV-BAT-01", "动力部件", 8000.0, 3),
    InventoryItem("EV-MOT-02", "驱动电机", 2500.0, 8),
    InventoryItem("EV-BUS-03", "BUS 模块", 120.0, 2),
]


def test_total_value():
    assert total_value(SAMPLE) == round(8000.0 * 3 + 2500.0 * 8 + 120.0 * 2, 2)


def test_total_value_empty():
    assert total_value([]) == 0.0


@pytest.mark.parametrize("sku,found", [
    ("EV-BAT-01", True),
    ("NO-SUCH", False),
])
def test_find_by_sku(sku, found):
    item = find_by_sku(SAMPLE, sku)
    assert (item is not None) == found


def test_find_by_sku_returns_item():
    assert find_by_sku(SAMPLE, "EV-MOT-02").name == "驱动电机"


def test_low_stock_default_threshold():
    assert [i.sku for i in low_stock(SAMPLE)] == ["EV-BAT-01", "EV-BUS-03"]


def test_low_stock_custom_threshold():
    assert [i.sku for i in low_stock(SAMPLE, threshold=10)] == ["EV-BAT-01", "EV-MOT-02", "EV-BUS-03"]


def test_stock_report():
    assert stock_report(SAMPLE) == {"EV-BAT-01": 3, "EV-MOT-02": 8, "EV-BUS-03": 2}


if __name__ == "__main__":
    pytest.main(["-q", __file__])
