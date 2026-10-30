"""依赖无关的文档解析。

数据分析场景最常见的输入是一张表（CSV / Excel），其次是 PDF。当前运行环境没有
pandas / openpyxl / pypdf，因此这里用标准库实现**只读预览级**解析：目标是让模型看到
表头、字段类型与前若干行，而不是完整还原工作簿格式。

生产环境如需高保真解析（合并单元格、公式、图像型 PDF），应通过 MCP 工具接入
pandas / openpyxl / pypdf 或文档解析服务；本模块的输出格式与其保持一致即可平滑替换。
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
import zlib
from typing import Literal

DocumentKind = Literal["csv", "xlsx", "pdf", "image", "text", "unsupported"]

_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
_TEXT_SUFFIXES = (".txt", ".md", ".json", ".log", ".yaml", ".yml")


def detect_kind(file_name: str, media_type: str | None) -> DocumentKind:
    """根据文件名与媒体类型判断文档种类。"""
    lowered = (media_type or "").lower()
    name = (file_name or "").lower()
    if lowered in _IMAGE_TYPES:
        return "image"
    if name.endswith(".csv") or lowered in {"text/csv", "application/csv"}:
        return "csv"
    if name.endswith((".xlsx", ".xlsm")) or lowered in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }:
        return "xlsx"
    if name.endswith(".pdf") or lowered == "application/pdf":
        return "pdf"
    if name.endswith(_TEXT_SUFFIXES) or lowered.startswith("text/"):
        return "text"
    return "unsupported"


def _decode(data: bytes) -> str:
    """按常见中文编码依次尝试解码，失败时用替换字符兜底。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _format_table(headers: list[str], rows: list[list[str]], *, max_rows: int) -> str:
    """把二维表渲染成 Markdown 表格，便于模型直接阅读。"""
    if not headers:
        return "（空表）"
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows[:max_rows]:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in padded) + " |")
    if len(rows) > max_rows:
        lines.append(f"\n（共 {len(rows)} 行，仅展示前 {max_rows} 行）")
    return "\n".join(lines)


def parse_csv(data: bytes, *, max_rows: int = 20) -> str:
    """解析 CSV：返回表头 + 前若干行。"""
    text = _decode(data)
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return "（空 CSV）"
    return _format_table(rows[0], rows[1:], max_rows=max_rows)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """读取 xlsx 的共享字符串表。"""
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    return [
        "".join(re.findall(r"<t[^>]*>(.*?)</t>", item, flags=re.DOTALL))
        for item in re.findall(r"<si>(.*?)</si>", raw.decode("utf-8"), flags=re.DOTALL)
    ]


def parse_xlsx(data: bytes, *, max_rows: int = 20) -> str:
    """解析 xlsx：取第一张工作表的前若干行（只读预览级，不还原样式/公式）。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid xlsx file") from exc
    shared = _xlsx_shared_strings(archive)
    sheet_name = next(
        (name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)),
        None,
    )
    if sheet_name is None:
        raise ValueError("xlsx has no worksheet")
    xml = archive.read(sheet_name).decode("utf-8")
    table: list[list[str]] = []
    for row_xml in re.findall(r"<row[^>]*>(.*?)</row>", xml, flags=re.DOTALL):
        cells: list[str] = []
        for cell_xml in re.findall(r"<c[^>]*?(?:/>|>.*?</c>)", row_xml, flags=re.DOTALL):
            cell_type = re.search(r't="([^"]+)"', cell_xml)
            value = re.search(r"<v>(.*?)</v>", cell_xml, flags=re.DOTALL)
            inline = re.search(r"<is>.*?<t[^>]*>(.*?)</t>.*?</is>", cell_xml, flags=re.DOTALL)
            if cell_type and cell_type.group(1) == "s" and value:
                index = int(value.group(1))
                cells.append(shared[index] if index < len(shared) else "")
            elif inline:
                cells.append(inline.group(1))
            elif value:
                cells.append(value.group(1))
            else:
                cells.append("")
        if any(cell.strip() for cell in cells):
            table.append(cells)
    if not table:
        return "（空工作表）"
    return _format_table(table[0], table[1:], max_rows=max_rows)


def _pdf_streams(data: bytes) -> list[bytes]:
    """取出 PDF 中可解码的流内容（FlateDecode 或未压缩）。"""
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.DOTALL):
        payload = match.group(1)
        try:
            streams.append(zlib.decompress(payload))
        except zlib.error:
            streams.append(payload)
    return streams


def parse_pdf(data: bytes, *, max_chars: int = 8000) -> str:
    """尽力提取 PDF 文本。

    只处理文本型 PDF 的 ``Tj`` / ``TJ`` 操作符；扫描版 PDF 没有文本层，会返回提示信息。
    生产环境应替换为 pypdf 或文档解析服务。
    """
    collected: list[str] = []
    for stream in _pdf_streams(data):
        for match in re.finditer(rb"\((?:[^()\\]|\\.)*\)", stream):
            raw = match.group(0)[1:-1]
            raw = re.sub(rb"\\([()\\])", rb"\1", raw)
            try:
                collected.append(raw.decode("latin-1"))
            except UnicodeDecodeError:  # pragma: no cover - latin-1 不会失败
                continue
        if sum(len(item) for item in collected) > max_chars:
            break
    text = re.sub(r"[ \t]+", " ", " ".join(collected)).strip()
    if not text:
        return "（未能从 PDF 中提取文本：可能是扫描件或该 PDF 使用了不支持的编码）"
    return text[:max_chars]


def extract_text(
    kind: DocumentKind, data: bytes, *, max_rows: int = 20, max_chars: int = 8000
) -> str:
    """按文档种类提取可读文本；不支持的类型返回明确说明。"""
    if kind == "csv":
        return parse_csv(data, max_rows=max_rows)
    if kind == "xlsx":
        return parse_xlsx(data, max_rows=max_rows)
    if kind == "pdf":
        return parse_pdf(data, max_chars=max_chars)
    if kind == "text":
        return _decode(data)[:max_chars]
    if kind == "image":
        return "（图片已作为多模态输入提供给模型，无需文本提取）"
    return "（不支持的文件类型）"
