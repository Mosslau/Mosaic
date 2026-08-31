# examples/ex06-report-export.py —— 数据合并与透视 + Excel / Markdown 报告导出
# 验证环境：Python 3.13.9，pandas 2.3.3，openpyxl 3.1.5，tabulate 0.9.0
# 运行：python3 ex06-report-export.py（离线可跑，已验证）；xlsx/md 产物写到系统临时目录
import tempfile
from pathlib import Path

import pandas as pd


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex06-"))

    # 1. 两张表：车辆档案 + 遥测记录（真实场景换成 read_csv 各自读取）
    fleet = pd.DataFrame(
        {"vehicle_id": ["V001", "V002", "V003"], "model": ["EV-A", "EV-B", "EV-A"]}
    )
    telemetry = pd.DataFrame(
        {
            "vehicle_id": ["V001", "V001", "V002", "V003", "V003", "V003"],
            "day": ["周一", "周二", "周一", "周一", "周二", "周三"],
            "mileage": [120.5, 135.0, 98.0, 150.2, 145.8, 88.4],
            "energy": [18.2, 20.1, 15.5, 22.0, 21.5, 13.8],
        }
    )

    # 2. 多表 join：按 vehicle_id 关联（how="left" 保留全部遥测记录）
    merged = telemetry.merge(fleet, on="vehicle_id", how="left")

    # 3. 分组统计：每车总里程、总能耗、出车次数、百公里能耗
    report = merged.groupby("vehicle_id").agg(
        total_mileage=("mileage", "sum"),
        total_energy=("energy", "sum"),
        trips=("day", "count"),
    )
    report["energy_per_100km"] = report["total_energy"] / report["total_mileage"] * 100
    report = report.round(2)
    print("每车汇总:")
    print(report)

    # 4. 透视表：车辆 × 日期的里程（长表变宽表，fill_value=0 防 NaN）
    pt = pd.pivot_table(
        merged, values="mileage", index="day", columns="vehicle_id", aggfunc="sum", fill_value=0
    )
    print("\n里程透视表:")
    print(pt)

    # 5. 导出报告：Excel 多 Sheet + Markdown 摘要
    #    index=False 防多余行号列；utf-8-sig 让 Excel 打开中文不乱码
    xlsx = outdir / "fleet_report.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        report.to_excel(writer, sheet_name="汇总")
        pt.to_excel(writer, sheet_name="里程透视")
    md = outdir / "fleet_report.md"
    md.write_text("# 车队能耗报告\n\n" + report.to_markdown(), encoding="utf-8")
    print("\n已导出:", xlsx, "存在:", xlsx.exists())
    print("已导出:", md, "存在:", md.exists())


if __name__ == "__main__":
    main()
