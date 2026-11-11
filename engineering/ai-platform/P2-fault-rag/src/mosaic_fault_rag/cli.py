"""AI 侧纵切入口。"""

import argparse
import sys
from typing import List, Optional

from .pipeline import run


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mosaic 故障诊断纵切（检索 + 引用 + 动作 + 反馈）")
    parser.add_argument("--limit", type=int, default=20, help="取最近 N 条故障事件")
    parser.add_argument("--threshold", type=float, default=0.12, help="检索分数低于该值判为无依据")
    parser.add_argument(
        "--verdict",
        default="correct",
        choices=["correct", "partial", "wrong", "unknown"],
        help="模拟业务结果（真实结果由业务系统回写）",
    )
    parser.add_argument("--actor", default="simulator")
    args = parser.parse_args(argv)

    try:
        run(limit=args.limit, verdict=args.verdict, threshold=args.threshold, actor=args.actor)
        return 0
    except Exception as exc:
        print("[rag] ERROR: %s" % exc, file=sys.stderr)
        print("  先起底座并跑数据侧纵切：engineering/infra/compose/up.sh && engineering/data-platform/P2-device-slice/slice.sh", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
