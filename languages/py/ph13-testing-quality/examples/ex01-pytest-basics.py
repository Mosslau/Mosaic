#!/usr/bin/env python3
# examples/ex01-pytest-basics.py —— pytest 基础：断言、异常测试、tmp_path、参数化
# 验证环境：Python 3.13.9 + pytest 8.4.2（本机已装并实测）
# 运行：python3 -m pytest ex01-pytest-basics.py -q（离线可跑，已验证）
#       或直接 python3 ex01-pytest-basics.py（等价：文件内 main 调用 pytest.main）
# 验证状态：已验证 —— 10 个用例全过（3 基础断言 + 1 tmp_path + 3 参数化 ×2 组）
# 本文件即一个 pytest 测试模块：生产函数与测试函数同文件，pytest 自动收集 test_ 开头的函数
import pytest


# ---- 被测代码（生产函数，主文档 3.1 的示例主体）----
def add(a: int, b: int) -> int:
    return a + b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b


def parse_score(line: str) -> tuple[str, int]:
    """解析 '姓名,成绩' 一行；格式非法或成绩越界（0~100）抛 ValueError。"""
    name, score = line.strip().split(",")
    s = int(score)
    if s < 0 or s > 100:
        raise ValueError(f"成绩越界: {s}")
    return name, s


# ---- 测试代码（pytest 约定：文件里 test_ 开头的函数才会被收集执行）----
def test_add_basic():
    assert add(1, 2) == 3          # 断言失败时 pytest 会打印两侧的实际值（见 4.1 断言重写）


def test_divide_normal():
    assert divide(10, 4) == 2.5


def test_divide_by_zero_raises():
    # pytest.raises 断言「应当抛出指定异常」，抛不出来算失败
    with pytest.raises(ValueError):
        divide(1, 0)


def test_parse_score_write_read(tmp_path):
    # tmp_path：pytest 内置 fixture，每个用例一个独立临时目录，用完自动清理（主文档 3.2）
    f = tmp_path / "scores.txt"
    f.write_text("Alice,88\nBob,72\n", encoding="utf-8")
    lines = f.read_text(encoding="utf-8").splitlines()
    assert parse_score(lines[0]) == ("Alice", 88)


@pytest.mark.parametrize("line,expected", [
    ("Alice,88", ("Alice", 88)),
    ("Bob,0", ("Bob", 0)),
    ("Carol,100", ("Carol", 100)),
])
def test_parse_score_parametrized(line, expected):
    # 参数化：一组数据展开成一个独立用例（主文档 3.4），失败时能精确定位是哪组数据
    assert parse_score(line) == expected


@pytest.mark.parametrize("line", ["Alice,", "Bob,120", "Carol,-5"])
def test_parse_score_invalid(line):
    with pytest.raises(ValueError):
        parse_score(line)


if __name__ == "__main__":
    pytest.main(["-q", __file__])
