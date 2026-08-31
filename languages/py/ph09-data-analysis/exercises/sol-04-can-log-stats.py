# exercises/sol-04-can-log-stats.py —— 练习 4 参考实现：CAN 日志统计
# 验证环境：Python 3.13.9；pandas 2.3.3 / matplotlib 3.10.6
# 运行：python3 sol-04-can-log-stats.py（离线可跑）
# 验证状态：已验证 —— 实测输出：频次 0x1A0=4 / 0x2B1=3 / 0x3C2=3；总报文 10、不同 ID 3；跳过脏行 1；PNG 约 25 KB
import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol04-"))

    # 1. 模拟 CAN 日志：11 行，其中 1 行格式损坏（真实场景换成 open("can.log").readlines()）
    log_text = """\
2024-06-01 08:00:00.100 CAN 0x1A0 DLC 8 7A 01 00 10 00 00 00 00
2024-06-01 08:00:00.110 CAN 0x2B1 DLC 8 00 10 50 00 00 00 00 00
2024-06-01 08:00:00.120 CAN 0x3C2 DLC 8 03 04 05 06 07 08 09 0A
2024-06-01 08:00:00.130 CAN 0x1A0 DLC 8 7B 01 00 10 00 00 00 00
2024-06-01 08:00:01.000 CAN 0x2B1 DLC 8 00 11 50 00 00 00 00 00
2024-06-01 08:00:01.010 CAN 0x1A0 DLC 8 7C 01 00 10 00 00 00 00
2024-06-01 08:00:01.020 CAN 0x3C2 DLC 8 04 04 05 06 07 08 09 0A
2024-06-01 08:00:02.000 CAN 0x1A0 DLC 8 7D 01 00 10 00 00 00 00
2024-06-01 08:00:02.010 CAN 0x2B1 DLC 8 00 12 50 00 00 00 00 00
2024-06-01 08:00:02.020 CAN 0x3C2 DLC 8 05 04 05 06 07 08 09 0A
2024-06-01 08:00:03.000 ERROR timeout            ← 脏行：不匹配正则，应跳过
"""
    # 正则：时间 + CAN ID（十六进制）+ DLC 与数据字节
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} [\d:.]+) CAN (0x[0-9A-Fa-f]+) DLC \d (.*)")
    rows = []
    skipped = 0
    for line in log_text.strip().splitlines():
        m = pattern.match(line)
        if m is None:
            skipped += 1
            continue
        ts, can_id, data = m.group(1), m.group(2), m.group(3)
        rows.append({"time": ts, "can_id": can_id, "byte0": int(data.split()[0], 16)})
    df = pd.DataFrame(rows)
    print("解析成功:", len(df), " 跳过脏行:", skipped)

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
    print("已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
