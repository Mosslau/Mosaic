# examples/ex05-can-log-stats.py —— CAN 日志统计：正则解析 + 按报文 ID 分组 + 频次分布图
# 验证环境：Python 3.13.9，pandas 2.3.3，matplotlib 3.10.6
# 运行：python3 ex05-can-log-stats.py（离线可跑，已验证）；PNG 产物写到系统临时目录
import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退；取列表里第一个已安装的
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 负号用 ASCII，避免字体缺失


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex05-"))

    # 1. 模拟 CAN 日志（真实场景换成 open("can.log").readlines()）
    log_text = """\
2024-06-01 08:00:00.123 CAN 0x123 DLC 8 78 5A 00 10 00 00 00 00
2024-06-01 08:00:00.125 CAN 0x456 DLC 8 00 00 50 00 00 00 00 00
2024-06-01 08:00:00.140 CAN 0x789 DLC 8 01 02 03 04 05 06 07 08
2024-06-01 08:00:00.155 CAN 0x123 DLC 8 80 5C 00 10 00 00 00 00
2024-06-01 08:00:01.000 CAN 0x123 DLC 8 82 5C 00 10 00 00 00 00
2024-06-01 08:00:01.020 CAN 0x456 DLC 8 00 00 50 00 00 00 00 00
2024-06-01 08:00:01.040 CAN 0x789 DLC 8 02 02 03 04 05 06 07 08
2024-06-01 08:00:02.000 CAN 0x123 DLC 8 84 5C 00 10 00 00 00 00
"""
    # 正则：时间 + CAN ID（十六进制）+ DLC 与数据字节
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} [\d:.]+) CAN (0x[0-9A-Fa-f]+) DLC \d (.*)")
    rows = []
    for line in log_text.strip().splitlines():
        m = pattern.match(line)
        if m is None:  # 解析失败的脏行直接跳过（真实日志中常见）
            continue
        ts, can_id, data = m.group(1), m.group(2), m.group(3)
        rows.append({"time": ts, "can_id": can_id, "byte0": int(data.split()[0], 16)})
    df = pd.DataFrame(rows)

    # 2. 按报文 ID 分组统计频次（size 统计组内行数，count 只统计非空值）
    freq = df.groupby("can_id").size().sort_values(ascending=False)
    print("各 CAN ID 报文频次:")
    print(freq)
    print("总报文数:", len(df), " 不同 ID 数:", df["can_id"].nunique())

    # 3. 频次分布柱状图：服务"哪些报文最频繁"的结论
    freq.plot.bar(figsize=(6, 4), color="seagreen")
    plt.title("CAN 报文频次分布")
    plt.ylabel("条数")
    plt.tight_layout()
    out = outdir / "can_freq.png"
    plt.savefig(out, dpi=150)
    print("已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
