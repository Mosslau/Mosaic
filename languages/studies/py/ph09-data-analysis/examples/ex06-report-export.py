# examples/ex06-report-export.py —— 多表 join + 分组汇总 + Excel / Markdown 报告导出
# 验证环境：Python 3.13.9，pandas 2.3.3，openpyxl 3.1.5，tabulate 0.9.0
# 运行：python3 ex06-report-export.py（离线可跑）；xlsx/md 产物写到系统临时目录
# 验证状态：已验证 —— python3 ex06-report-export.py：S001 25500 请求 / 错误率 0.08%、S002 9800 /
#           0.41%、S003 38300 / 0.09%；svc_report.xlsx 与 svc_report.md 均生成（产物在临时目录）
"""平台服务日报：服务档案表与每日指标表 join 后分组汇总，再导出 Excel 与 Markdown。

对应主文档 3.6 / 3.7 / 3.9 与第 6 章「示例 5」：
- join：指标表左连服务档案表，补上「所属团队」维度（多表先想主键与保留方向）；
- groupby：每实例总请求数、总错误数、平均延迟、统计天数与错误率；
- pivot_table：日期 × 实例的请求量（长表变宽表，`fill_value=0` 防 NaN）；
- 导出：Excel 两个 Sheet + Markdown 摘要（`index=False` 防多余行号列）。
"""

import tempfile
from pathlib import Path

import pandas as pd


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex06-"))

    # 1. 两张表：服务档案 + 每日指标（真实场景换成 read_csv 各自读取）
    registry = pd.DataFrame(
        {"service_id": ["S001", "S002", "S003"], "team": ["平台组", "平台组", "数据组"]}
    )
    daily = pd.DataFrame(
        {
            "service_id": ["S001", "S001", "S002", "S003", "S003", "S003"],
            "day": ["周一", "周二", "周一", "周一", "周二", "周三"],
            "requests": [12000, 13500, 9800, 15000, 14500, 8800],
            "errors": [12, 9, 40, 15, 11, 7],
            "latency_ms": [42.5, 45.1, 88.0, 60.2, 58.4, 55.0],
        }
    )

    # 2. 日期是有序维度：转 ordered Categorical，透视表才按「周一→周三」而不是字典序排列
    daily["day"] = pd.Categorical(
        daily["day"], categories=["周一", "周二", "周三"], ordered=True
    )

    # 3. 多表 join：按 service_id 关联（how="left" 保留全部指标记录）
    merged = daily.merge(registry, on="service_id", how="left")

    # 4. 分组统计：每实例总请求、总错误、平均延迟、统计天数、错误率
    report = merged.groupby("service_id").agg(
        total_requests=("requests", "sum"),
        total_errors=("errors", "sum"),
        avg_latency_ms=("latency_ms", "mean"),
        days=("day", "count"),
    )
    report["error_pct"] = report["total_errors"] / report["total_requests"] * 100
    report = report.round(2)
    print("每实例汇总:")
    print(report)

    # 5. 透视表：日期 × 实例的请求量（长表变宽表，fill_value=0 防 NaN）
    pt = pd.pivot_table(
        merged,
        values="requests",
        index="day",
        columns="service_id",
        aggfunc="sum",
        fill_value=0,
        observed=False,  # 日期是有序 Categorical：保留全部日期行，未出现的组合填 0
    )
    print("\n请求量透视表:")
    print(pt)

    # 6. 导出报告：Excel 多 Sheet + Markdown 摘要
    #    index=False 防多余行号列；utf-8 让 Excel / 编辑器打开中文不乱码
    xlsx = outdir / "svc_report.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        report.to_excel(writer, sheet_name="汇总")
        pt.to_excel(writer, sheet_name="请求透视")
    md = outdir / "svc_report.md"
    md.write_text("# 平台服务日报\n\n" + report.to_markdown(), encoding="utf-8")
    print("\n已导出:", xlsx, "存在:", xlsx.exists())
    print("已导出:", md, "存在:", md.exists())


if __name__ == "__main__":
    main()
