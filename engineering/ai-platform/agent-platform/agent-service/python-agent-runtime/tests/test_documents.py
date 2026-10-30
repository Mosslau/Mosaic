"""文档解析的单元测试（CSV / XLSX / PDF / 文本）。

解析器不依赖 pandas/openpyxl/pypdf，因此用构造的最小文件验证行为边界。
"""

import io
import zipfile

import pytest

from data_agent_runtime.runtime.documents import (
    detect_kind,
    extract_text,
    parse_csv,
    parse_pdf,
    parse_xlsx,
)


def test_detect_kind_by_name_and_media_type():
    """验证常见类型能被正确识别，未知类型归为 unsupported。"""
    assert detect_kind("data.csv", None) == "csv"
    assert detect_kind("a.xlsx", None) == "xlsx"
    assert detect_kind("report.pdf", "application/pdf") == "pdf"
    assert detect_kind("shot.png", "image/png") == "image"
    assert detect_kind("notes.txt", None) == "text"
    assert detect_kind("archive.bin", "application/octet-stream") == "unsupported"


def test_parse_csv_renders_markdown_table():
    """验证 CSV 被渲染成含表头与数据行的 Markdown 表格。"""
    table = parse_csv("车型,数量\nNQi GT,128\nNQi,64\n".encode())
    assert "| 车型 | 数量 |" in table
    assert "| NQi GT | 128 |" in table


def test_parse_csv_truncates_and_reports_total():
    """验证超过预览行数时给出截断提示。"""
    rows = "a,b\n" + "".join(f"{i},{i}\n" for i in range(30))
    table = parse_csv(rows.encode(), max_rows=5)
    assert "仅展示前 5 行" in table


def test_parse_csv_handles_gbk_encoding():
    """验证非 UTF-8 的中文 CSV 不会解析失败。"""
    table = parse_csv("车型,数量\nNQi GT,128\n".encode("gb18030"))
    assert "NQi GT" in table


def _minimal_xlsx() -> bytes:
    """构造一个含共享字符串与数字的最小 xlsx。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            "<sst><si><t>车型</t></si><si><t>数量</t></si><si><t>NQi</t></si></sst>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet><sheetData>'
            '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
            '<row><c t="s"><v>2</v></c><c><v>128</v></c></row>'
            "</sheetData></worksheet>",
        )
    return buffer.getvalue()


def test_parse_xlsx_reads_shared_strings_and_numbers():
    """验证 xlsx 能解析共享字符串与数值单元格。"""
    table = parse_xlsx(_minimal_xlsx())
    assert "| 车型 | 数量 |" in table
    assert "NQi" in table and "128" in table


def test_parse_xlsx_rejects_invalid_archive():
    """验证损坏的 xlsx 抛出可读错误，而不是静默返回空。"""
    with pytest.raises(ValueError, match="invalid xlsx"):
        parse_xlsx(b"not a zip")


def test_parse_pdf_extracts_text_operators():
    """验证能从含文本操作符的 PDF 流中提取文字。"""
    pdf = b"%PDF-1.4\nstream\nBT (Hello Data) Tj ET\nendstream"
    assert "Hello Data" in parse_pdf(pdf)


def test_parse_pdf_reports_scanned_document():
    """验证没有文本层时给出明确提示，而不是返回空字符串。"""
    assert "未能从 PDF 中提取文本" in parse_pdf(b"%PDF-1.4\nstream\nendstream")


def test_extract_text_dispatch():
    """验证按类型分派：图片与未知类型给出说明文本。"""
    assert "多模态" in extract_text("image", b"")
    assert "不支持" in extract_text("unsupported", b"")
    assert extract_text("text", "纯文本".encode()) == "纯文本"
