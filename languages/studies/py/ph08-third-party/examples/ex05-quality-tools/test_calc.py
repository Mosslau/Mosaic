# examples/ex05-quality-tools/test_calc.py —— 主文档 6.5：pytest fixture + 参数化测试
# 运行（在 ex05-quality-tools/ 目录下）：pytest -q（已验证，6 个用例全过）
import pytest

from calc import add, parse_speed


@pytest.fixture
def speeds() -> list[float]:
    return [80.0, 95.0, 60.0]  # fixture：每个用例独立的新对象


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (1, 2, 3),
        (0, 0, 0),
        (-1, 1, 0),
    ],
)
def test_add(a, b, expected):
    assert add(a, b) == expected


def test_parse_speed_ok():
    assert parse_speed("80") == 80.0


def test_parse_speed_bad():
    with pytest.raises(ValueError):
        parse_speed("abc")


def test_speeds_fixture(speeds):
    assert len(speeds) == 3
