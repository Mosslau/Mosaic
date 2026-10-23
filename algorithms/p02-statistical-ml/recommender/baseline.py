"""推荐系统 — 流行度基线。"""

from impl import Popularity


def run_baseline(R):
    return Popularity().fit(R)


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，由 demo.py 调用")
