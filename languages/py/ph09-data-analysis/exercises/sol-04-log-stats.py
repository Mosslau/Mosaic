# exercises/sol-04-log-stats.py —— 练习 4 参考实现：平台服务日志统计
# 验证环境：Python 3.13.9；pandas 2.3.3 / matplotlib 3.10.6
# 运行：python3 sol-04-log-stats.py（离线可跑）
# 验证状态：已验证 —— python3 sol-04-log-stats.py：解析成功 10 行 / 跳过脏行 1；来源频次 svc-001=4 /
#           svc-002=3 / svc-003=3；log_freq.png 26199 字节（产物在临时目录）
"""练习 4 参考实现：解析平台服务日志文本，按来源与级别分组统计并画分布图。

与 examples/ex05 同题不同参：11 行样本、其中 1 行格式损坏应跳过；覆盖 3 个来源。
"""

import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能 savefig，不弹 GUI
import matplotlib.pyplot as plt
import pandas as pd

# 中文字体回退链：macOS 用 PingFang/Hiragino，Linux/Windows 依次回退
plt.rcParams["font.sans-serif"] = [
    "PingFang HK",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
]
plt.rcParams["axes.unicode_minus"] = False

# 平台服务日志行：时间 级别 来源 消息（级别限定三档，便于按级别分组）
LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} [\d:.]+)\s+(INFO|WARN|ERROR)\s+(\S+)\s+(.*)"
)


def main() -> None:
    outdir = Path(tempfile.mkdtemp(prefix="ph09-sol04-"))

    # 1. 模拟平台服务日志：11 行，其中 1 行格式损坏（真实场景换成 open("platform.log")）
    log_text = """\
2024-06-01 08:00:00.100 INFO svc-001 request handled latency=40ms
2024-06-01 08:00:00.110 WARN svc-002 cpu 91%
2024-06-01 08:00:00.120 ERROR svc-003 upstream timeout
2024-06-01 08:00:00.130 INFO svc-001 request handled latency=44ms
2024-06-01 08:00:01.000 WARN svc-002 mem usage 93%
2024-06-01 08:00:01.010 INFO svc-001 request handled latency=47ms
2024-06-01 08:00:01.020 ERROR svc-003 upstream timeout
2024-06-01 08:00:02.000 INFO svc-001 request handled latency=52ms
2024-06-01 08:00:02.010 WARN svc-002 disk temp high 78C
2024-06-01 08:00:02.020 ERROR svc-003 upstream timeout
2024-06-01 08:00:03.000 heartbeat lost            ← 脏行：不匹配正则，应跳过
"""
    rows = []
    skipped = 0
    for line in log_text.strip().splitlines():
        m = LOG_PATTERN.match(line)
        if m is None:
            skipped += 1
            continue
        ts, level, source, message = m.groups()
        rows.append({"ts": ts, "level": level, "source": source, "message": message})
    df = pd.DataFrame(rows)
    print("解析成功:", len(df), " 跳过脏行:", skipped)

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
    print(
        "\n已保存:", out, " 存在:", out.exists(), " 大小:", out.stat().st_size, "字节"
    )


if __name__ == "__main__":
    main()
