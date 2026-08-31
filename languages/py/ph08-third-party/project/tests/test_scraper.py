# project/tests/test_scraper.py —— 离线测试：内置 HTML fixture 覆盖解析与 CSV 写出
# 运行（在 project/ 目录下）：pytest -q（已验证，4 个用例全过，不依赖网络）
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 导入平级的 scraper.py

from scraper import SAMPLE_HTML, main, parse_page, save_csv  # noqa: E402


@pytest.fixture
def parsed() -> dict:
    """用内置样例 HTML 解析一次，供多个用例复用。"""
    return parse_page(SAMPLE_HTML, "https://demo.local/")


def test_parse_title(parsed):
    assert parsed["title"] == "样例页面"


def test_parse_links_dedup_and_absolute(parsed):
    # 重复的 /about 应去重；相对链接应转为绝对地址
    assert parsed["links"] == [
        "https://demo.local/about",
        "https://example.com/doc",
    ]


def test_parse_table_rows(parsed):
    assert parsed["table_rows"][0] == ["vehicle_id", "speed"]
    assert parsed["table_rows"][1] == ["V001", "80"]
    assert len(parsed["table_rows"]) == 3


def test_save_csv_roundtrip(parsed, tmp_path):
    out = tmp_path / "out.csv"
    save_csv([parsed], str(out))
    with open(out, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["url", "title", "kind", "value"]
    kinds = {row[2] for row in rows[1:]}
    assert kinds == {"link", "table_row"}
    # 2 条链接 + 3 行表格 = 5 行数据
    assert len(rows) == 1 + 5


def test_demo_mode_offline(tmp_path, capsys):
    out = tmp_path / "demo.csv"
    assert main(["--demo", "-o", str(out)]) == 0
    assert out.exists()
    assert "样例页面" in capsys.readouterr().out
