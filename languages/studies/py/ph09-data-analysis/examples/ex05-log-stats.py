# examples/ex05-log-stats.py —— 平台服务日志统计：正则解析 + 按来源/级别分组 + 频次分布图
# 验证环境：Python 3.13.9，pandas 2.3.3，matplotlib 3.10.6
# 运行：python3 ex05-log-stats.py（离线可跑）；PNG 产物写到系统临时目录
# 验证状态：已验证 —— python3 ex05-log-stats.py：解析 8 行、3 个不同来源；来源频次 svc-001=4 /
#           svc-002=2 / svc-003=2；log_freq.png 26212 字节（产物在临时目录）
"""平台服务日志统计：一行一条日志，字段为「时间 + 级别 + 来源 + 消息」。

对应主文档 3.2 的文本解析与 3.5 的分组统计：用一条正则一次提取时间、级别
（INFO/WARN/ERROR）与来源（svc-XXX），再按来源统计活跃度、按级别看分布，最后画
来源频次柱状图。解析失败的脏行直接跳过，不中断整批统计。
"""

import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退；取列表里第一个已安装的
plt.rcParams["font.sans-serif"] = [
    "PingFang HK",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 负号用 ASCII，避免字体缺失

# 平台服务日志行：时间 级别 来源 消息（级别限定三档，便于按级别分组）
LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} [\d:.]+)\s+(INFO|WARN|ERROR)\s+(\S+)\s+(.*)"
)


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-ex05-"))

    # 1. 模拟平台服务日志（真实场景换成 open("platform.log").readlines() 逐行处理）
    log_text = """\
2024-06-01 08:00:00.123 INFO svc-001 request handled latency=42ms
2024-06-01 08:00:00.125 WARN svc-002 mem usage 92%
2024-06-01 08:00:00.140 ERROR svc-003 upstream timeout
2024-06-01 08:00:00.155 INFO svc-001 request handled latency=45ms
2024-06-01 08:00:01.000 INFO svc-001 request handled latency=51ms
2024-06-01 08:00:01.020 WARN svc-002 disk temp high 76C
2024-06-01 08:00:01.040 ERROR svc-003 upstream timeout
2024-06-01 08:00:02.000 INFO svc-001 request handled latency=48ms
"""
    rows = []
    for line in log_text.strip().splitlines():
        m = LOG_PATTERN.match(line)
        if m is None:  # 解析失败的脏行直接跳过（真实日志中常见）
            continue
        ts, level, source, message = m.groups()
        rows.append({"ts": ts, "level": level, "source": source, "message": message})
    df = pd.DataFrame(rows)

    # 2. 按来源分组统计频次（size 统计组内行数，count 只统计非空值）
    freq = df.groupby("source").size().sort_values(ascending=False)
    print("各来源日志条数:")
    print(freq)
    # 3. 按级别看分布，再交叉成「来源 × 级别」透视表
    print("\n各日志级别条数:")
    print(df.groupby("level").size().sort_values(ascending=False))
    pt = pd.pivot_table(
        df,
        values="message",
        index="source",
        columns="level",
        aggfunc="count",
        fill_value=0,
    )
    print("\n来源 × 级别 条数透视表:")
    print(pt)
    print("\n总日志条数:", len(df), " 不同来源数:", df["source"].nunique())

    # 4. 频次分布柱状图：服务"哪些来源最活跃"的结论
    freq.plot.bar(figsize=(6, 4), color="steelblue")
    plt.title("平台服务日志来源分布")
    plt.ylabel("条数")
    plt.tight_layout()
    out = outdir / "log_freq.png"
    plt.savefig(out, dpi=150)
    print("\n已保存:", out)
    print("文件存在:", out.exists(), " 大小:", out.stat().st_size, "字节")


if __name__ == "__main__":
    main()
