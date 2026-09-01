#!/usr/bin/env python3
# examples/ex01-batch-files.py —— 文件批处理：pathlib 批量归档日志文件（幂等 + 审计日志）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex01-batch-files.py（离线可跑，已验证；样本文件与归档目录都在系统临时目录）
# 说明：对应主文档 3.1 与 roadmap「示例」。把 app-YYYYMMDD.log 批量归档到 archive/YYYY-MM/：
#       目标已存在则跳过（可安全重跑），每个动作写审计日志（可审计），非日志文件不动。
import logging
import re
import shutil
import tempfile
from pathlib import Path

DATE_RE = re.compile(r"app-(\d{4})(\d{2})(\d{2})\.log$")


def make_sample(src: Path) -> list[str]:
    """造 4 个样本文件：3 个日志（分属 2026-09 / 2026-10）+ 1 个无关 txt。"""
    names = ["app-20260901.log", "app-20260915.log", "app-20261003.log", "notes.txt"]
    for name in names:
        (src / name).write_text(f"sample content of {name}\n", encoding="utf-8")
    return names


def archive(src: Path, dest_root: Path, logger: logging.Logger) -> dict[str, int]:
    """把 src 下 app-YYYYMMDD.log 归档到 dest_root/YYYY-MM/，返回动作统计。"""
    stats = {"moved": 0, "already": 0, "skipped": 0}
    for p in sorted(src.iterdir()):  # iterdir 遍历全部条目：*.log 之外的也要统计
        if p.is_dir() or p.suffix != ".log":
            stats["skipped"] += 1
            logger.info("SKIP 非日志文件: %s", p.name)
            continue
        m = DATE_RE.search(p.name)
        if m is None:
            stats["skipped"] += 1
            logger.info("SKIP 非日期命名: %s", p.name)
            continue
        month_dir = dest_root / f"{m.group(1)}-{m.group(2)}"
        month_dir.mkdir(parents=True, exist_ok=True)
        target = month_dir / p.name
        if target.exists():  # 幂等：目标已在 → 跳过，不覆盖不重复
            stats["already"] += 1
            logger.info("ALREADY 已归档: %s", target.name)
            continue
        shutil.move(str(p), str(target))
        stats["moved"] += 1
        logger.info("MOVE %s -> %s", p.name, target.relative_to(dest_root))
    return stats


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-ex01-"))
    src = work / "src"
    src.mkdir()
    audit = work / "audit.log"
    logging.basicConfig(  # 审计日志：每个文件动作都留痕，脚本可重放可追溯
        filename=audit, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("batch")

    print("样本文件:", ", ".join(make_sample(src)))
    archive_dir = work / "archive"

    stats1 = archive(src, archive_dir, logger)
    print("第一次运行 -> 移动:", stats1["moved"],
          "| 已存在跳过:", stats1["already"],
          "| 非日志跳过:", stats1["skipped"])

    make_sample(src)  # 模拟同一批日志再次出现（重复跑同一脚本）
    stats2 = archive(src, archive_dir, logger)
    print("第二次运行 -> 移动:", stats2["moved"],
          "| 已存在跳过:", stats2["already"],
          "| 非日志跳过:", stats2["skipped"])

    archived = sorted(str(p.relative_to(work)) for p in archive_dir.rglob("*.log"))
    print("归档文件:", ", ".join(archived))
    print("审计日志行数:", len(audit.read_text(encoding="utf-8").strip().splitlines()))
    print("工作目录:", work)


if __name__ == "__main__":
    main()
