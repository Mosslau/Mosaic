#!/usr/bin/env python3
# exercises/sol-01-batch-logs.py —— 练习 1 参考实现：批量整理日志（pathlib + 归档 + 清理）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 sol-01-batch-logs.py（离线可跑，已验证；样本与归档都在系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 实际运行）：
#   整理前 -> 文件 6 个（日志 4 + 临时 2），日志总大小 1651 字节
#   按文件名日期归档（2026-09-01 之前 -> archive/）-> 移动 2 个
#   清理临时文件 -> 删除 2 个（*.tmp）
#   整理后 -> logs 下剩余日志 2 个；archive 下 2 个
#   再次运行 -> 移动 0 个、删除 0 个（幂等，可安全重跑）
#   整理报告 -> report.csv 3 行（含表头）；审计日志 audit.log 4 行（2 MOVE + 2 DELETE）
import csv
import logging
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

LOG_NAME_RE = re.compile(r"app-(\d{4})-(\d{2})-(\d{2})\.log$")


def make_sample(logs: Path) -> None:
    """造 6 个样本文件：4 个日志（2 旧 2 新）+ 2 个 *.tmp 临时文件。"""
    sizes = {  # (文件名, 内容字节数)
        "app-2026-08-01.log": 420,
        "app-2026-08-15.log": 380,
        "app-2026-09-01.log": 260,
        "app-2026-09-15.log": 591,
        "cache.tmp": 88,
        "temp.tmp": 64,
    }
    for name, size in sizes.items():
        (logs / name).write_text("x" * size, encoding="utf-8")


def audit_log_path(work: Path) -> Path:
    logging.basicConfig(  # 审计日志：每个动作一行，可追溯
        filename=work / "audit.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return work / "audit.log"


def organize(logs: Path, archive: Path, cutoff: date, logger: logging.Logger) -> dict[str, int]:
    """归档 cutoff 之前的日志、删除 *.tmp；返回动作统计。幂等：再跑一遍全是 0。"""
    stats = {"moved": 0, "deleted": 0}
    for p in sorted(logs.iterdir()):
        m = LOG_NAME_RE.search(p.name)
        if m is not None:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d < cutoff:  # 旧日志 -> 归档
                archive.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(archive / p.name))
                stats["moved"] += 1
                logger.info("MOVE %s -> archive/", p.name)
        elif p.suffix == ".tmp":  # 临时文件 -> 删除
            p.unlink()
            stats["deleted"] += 1
            logger.info("DELETE %s", p.name)
    return stats


def write_report(logs: Path, archive: Path, report: Path) -> None:
    rows = []
    for label, d in (("logs", logs), ("archive", archive)):
        files = sorted(d.glob("*.log"))
        total = sum(f.stat().st_size for f in files)
        rows.append((label, len(files), total))
    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["位置", "日志数", "总字节"])
        writer.writerows(rows)


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-sol01-"))
    logs = work / "logs"
    archive = work / "archive"
    logs.mkdir()
    make_sample(logs)
    audit = audit_log_path(work)  # 审计日志初始化（首次 organize 前调用）
    logger = logging.getLogger("organize")

    before = sorted(logs.glob("*.log"))
    print("整理前 -> 文件", len(before) + len(list(logs.glob("*.tmp"))),
          "个（日志", len(before), "+ 临时 2），日志总大小",
          sum(f.stat().st_size for f in before), "字节")

    stats1 = organize(logs, archive, date(2026, 9, 1), logger)
    print("第一次整理 -> 归档旧日志:", stats1["moved"], "个 | 删除临时文件:", stats1["deleted"], "个")

    after = sorted(logs.glob("*.log"))
    print("整理后 -> logs 剩余日志:", len(after), "个 | archive 归档:", len(list(archive.glob("*.log"))), "个")

    stats2 = organize(logs, archive, date(2026, 9, 1), logger)
    print("再次运行 -> 归档:", stats2["moved"], "个 | 删除:", stats2["deleted"], "个（幂等）")

    report = work / "report.csv"
    write_report(logs, archive, report)
    print("整理报告 ->", report, "（", len(report.read_text(encoding="utf-8").splitlines()),
          "行，含表头）")
    print("审计日志行数 ->", len(audit.read_text(encoding="utf-8").strip().splitlines()))


if __name__ == "__main__":
    main()
