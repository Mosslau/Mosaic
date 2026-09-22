# project/platdash/report.py —— Matplotlib 图表 + 自包含 HTML Dashboard + JSON
# 验证环境：Python 3.13 + pandas + matplotlib；本机实测 Python 3.13.9 + matplotlib（见 README）
"""展示层：把 analyze 的数字变成「可分发、可归档」的产物。

- 图表：Matplotlib Agg 后端（无显示环境可跑）+ 中文字体回退链（与 ex04 同法）
- HTML：图片 base64 内嵌 → 单文件自包含，邮件/归档/CI 附件皆可用
- JSON：`dashboard.json` 给 API/BI 消费（结构化摘要与 HTML 分离）
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from platdash.analyze import platform_summary, platform_table

# 中文图表字体回退（macOS PingFang/Hiragino → Linux Noto → Windows 微软雅黑）
_CJK_FONTS = (
    "PingFang SC",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
)


def _setup_font() -> None:
    from matplotlib import font_manager, rcParams

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_FONTS:
        if name in installed:
            rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            rcParams["axes.unicode_minus"] = False
            return


def _chart_platform_bars(table: pd.DataFrame) -> Path:
    """单实例数据传输量 + 平均磁盘温度双柱状图。"""
    _setup_font()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
    vids = table["service_id"].tolist()
    ax1.bar(vids, table["traffic_gb"], color="#2980b9")
    ax1.set_title("单实例数据传输量（GB）")
    ax1.set_ylabel("传输量 GB")
    ax2.bar(vids, table["mean_disk_temp_c"], color="#e67e22")
    ax2.set_title("单实例平均磁盘温度（℃）")
    ax2.set_ylabel("温度 ℃")
    fig.tight_layout()
    return _save(fig, "platform_bars.png")


def _chart_latency_trend(df: pd.DataFrame, window_s: int = 300) -> Path:
    """每实例前 window_s 秒延迟曲线（用于人眼抽查数据质量）。"""
    _setup_font()
    fig, ax = plt.subplots(figsize=(10, 3.6))
    for vid, grp in df.groupby("service_id"):
        head = grp.sort_values("ts").head(window_s)
        ax.plot((head["ts"] - head["ts"].min()) / 60.0, head["latency_ms"], label=vid)
    ax.set_title(f"延迟曲线（前 {window_s // 60} 分钟）")
    ax.set_xlabel("时间（分钟）")
    ax.set_ylabel("延迟 ms")
    ax.legend()
    fig.tight_layout()
    return _save(fig, "latency_trend.png")


def _save(fig: plt.Figure, name: str) -> Path:
    # 临时存 PNG（默认 /tmp，绕开受限环境的默认 TMPDIR），随后被 HTML 以 base64 内嵌
    import os
    import tempfile

    fd, path = tempfile.mkstemp(prefix="platdash_", suffix=".png", dir="/tmp")
    os.close(fd)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return Path(path)


def _png_to_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    path.unlink()  # 内嵌完成即清理临时 PNG
    return f"data:image/png;base64,{encoded}"


def _render_html(
    title: str, platform: dict[str, object], table: pd.DataFrame, charts: list[tuple[str, str]]
) -> str:
    rows = "\n".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>"
        for r in table.itertuples(index=False, name=None)
    )
    imgs = "".join(
        f'<h3>{name}</h3><img src="{uri}" style="max-width:100%"/>' for name, uri in charts
    )
    summary = (
        f"平台 {platform['services']} · 总数据传输量 <b>{platform['total_traffic_gb']} GB</b>"
        f" · 总耗电量 <b>{platform['total_energy_kwh']} kWh</b>"
    )
    return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       margin: 2rem auto; max-width: 980px; color: #222; }}
h1 {{ border-bottom: 2px solid #2980b9; padding-bottom: .3rem; }}
table {{ border-collapse: collapse; width: 100%; margin: .6rem 0 1.5rem; }}
th, td {{ border: 1px solid #ccc; padding: .35rem .5rem; text-align: right; }}
th {{ background: #ecf0f1; }}
</style></head>
<body>
<h1>{title}</h1>
<p>{summary}</p>
{imgs}
<h2>单实例汇总</h2>
<table>
<tr><th>{"</th><th>".join(table.columns)}</th></tr>
{rows}
</table>
</body></html>
"""


def build_dashboard(df: pd.DataFrame, out_dir: str | Path) -> dict[str, str]:
    """主入口：清洗后的 df → 图表/HTML/JSON 写 out_dir，返回产物路径映射。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    platform = platform_summary(df)
    table = platform_table(df)
    platform_bars = _chart_platform_bars(table)
    latency_trend = _chart_latency_trend(df)
    charts = [
        ("数据传输量与平均磁盘温度", _png_to_data_uri(platform_bars)),
        ("延迟曲线", _png_to_data_uri(latency_trend)),
    ]
    html = _render_html("平台指标 Dashboard", platform, table, charts)
    html_path = out_dir / "dashboard.html"
    html_path.write_text(html, encoding="utf-8")
    json_path = out_dir / "dashboard.json"
    json_path.write_text(json.dumps(platform, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "html": str(html_path),
        "json": str(json_path),
    }
