#!/usr/bin/env python3
"""为实验目录生成素材生成器骨架（make_teaching_assets.py）——纪律④的起手式。

用法（在仓库根执行，脚本路径下同）：
    python3 .dsh/skills/mindspring-lab/scripts/scaffold_assets.py algorithms/<族>/<算法名>
    ... <实验目录> --check    # 只检查已存在的生成器是否合规
    ... <实验目录> --force    # 覆盖已有文件

做三件事：
1. 校验目标目录（必须在 algorithms/ 下，且已有 impl.py 或 demo.py——素材必须与实现对账）
2. 生成 make_teaching_assets.py：缓存/字体初始化 + 对账断言 verify() 空壳 + 四类素材的空壳
3. 创建 images/ 目录

不做什么：具体画什么图、断言哪些数字由实验作者填——脚手架只保证"可重跑 + 可对账"这条底线。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
assert (ROOT / "algorithms").is_dir(), f"仓库根定位失败：{ROOT}"

GENERATOR = "make_teaching_assets.py"

TEMPLATE = '''"""{name} 图文素材生成器（供 README 基础篇 / 进阶篇引用）。

原则：素材全部由本脚本生成，且与实现逐项对账（纪律④）——对不上直接报错、不出图。
产出（images/）：01-概念图.png / 02-主循环.png / 03-对比图.png / 04-动画.gif
运行：cd {rel} && ../../../.venv/bin/python {gen}
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")  # 只读环境下的缓存兜底

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import animation, font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)

# 中文字体：找不到就直接报错，避免图里出现"方块"
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
FONT = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
if FONT is None:
    raise SystemExit("找不到中文字体（Noto / 文泉驿），装一个再跑")
font_manager.fontManager.addfont(FONT)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False

# TODO: 导入本实验的实现与对照入口（函数名按 impl.py / baseline.py 实际改）
# from impl import <主函数>
# from baseline import <对照函数>
# from demo import <造数据函数>


def verify() -> None:
    """素材与实现对账：数字不一致直接报错（纪律④的机器保险）。

    写法：用与图里完全相同的数据跑一遍实现，逐项断言。
    """
    # ref = <主函数>(...)
    # assert <素材算出的数> == ref.<对应字段>, "扩展数与 impl 不一致"
    raise NotImplementedError("先写 verify()：素材数字必须与实现对账")


def make_concept() -> None:
    """01 概念图：核心量与规则（基础篇 1–2 节）。"""
    raise NotImplementedError


def make_flow() -> None:
    """02 流程图：主循环（基础篇 3 节）。能用 Mermaid 写的，不必出 PNG（见 visual-assets.md）。"""
    raise NotImplementedError


def make_compare() -> None:
    """03 对比图：手写 vs 对照 / 参数扫描（基础篇 6 节、进阶篇「对照」段）。"""
    raise NotImplementedError


def make_animation() -> None:
    """04 动画：过程与顺序（基础篇 4/6 节）。GIF 控制在 2 MB 以内。"""
    # anim = animation.FuncAnimation(fig, update, frames=range(0, n, 6))
    # anim.save(IMAGES / "04-动画.gif", writer=animation.PillowWriter(fps=8))
    raise NotImplementedError


if __name__ == "__main__":
    verify()
    for step in (make_concept, make_flow, make_compare, make_animation):
        try:
            step()
        except NotImplementedError:
            print(f"· 跳过未实现的 {{step.__name__}}")
    print("素材输出到", IMAGES)
'''


def rel_to_root(unit: Path) -> str:
    return unit.relative_to(ROOT).as_posix()


def check(unit: Path, rel: str) -> list[str]:
    """检查已存在的生成器是否具备底线要素。"""
    path = unit / GENERATOR
    if not path.exists():
        return [f"{rel}：缺少 {GENERATOR}（先跑脚手架生成，或手写一个）"]
    src = path.read_text(encoding="utf-8")
    problems = []
    if "assert" not in src:
        problems.append(f"{rel}/{GENERATOR}：没有对账断言（assert）——素材数字无法与实现互证")
    if "MPLCONFIGDIR" not in src:
        problems.append(f"{rel}/{GENERATOR}：缺少 MPLCONFIGDIR 兜底——只读环境下会报缓存错误")
    if "font_manager" not in src:
        problems.append(f"{rel}/{GENERATOR}：缺少中文字体注册——图里会出现方块")
    if not (unit / "images").is_dir():
        problems.append(f"{rel}：缺少 images/ 目录（生成器应创建它）")
    return problems


def scaffold(unit: Path, rel: str, force: bool) -> int:
    if not unit.is_dir():
        print(f"✗ 目录不存在：{rel}", file=sys.stderr)
        return 1
    if not rel.startswith("algorithms/"):
        print(f"✗ 目标必须在 algorithms/ 下：{rel}", file=sys.stderr)
        return 1
    sources = [p.name for p in (unit / "impl.py", unit / "demo.py") if p.exists()]
    if not sources:
        print(f"✗ {rel} 里没有 impl.py / demo.py——素材必须与实现对账，先写实现", file=sys.stderr)
        return 1

    path = unit / GENERATOR
    if path.exists() and not force:
        print(f"· {rel}/{GENERATOR} 已存在（用 --force 覆盖，或 --check 检查）")
        return 0

    path.write_text(
        TEMPLATE.format(name=unit.name, rel=rel, gen=GENERATOR), encoding="utf-8"
    )
    (unit / "images").mkdir(exist_ok=True)
    print(f"✓ 已生成 {rel}/{GENERATOR}（检测到：{', '.join(sources)}）")
    print("  下一步：写 verify() 的对账断言 → 再填四类素材 → 运行脚本")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成实验的素材生成器骨架")
    parser.add_argument("unit", help="实验目录，如 algorithms/p01-search/mcts")
    parser.add_argument("--check", action="store_true", help="只检查已有生成器是否合规")
    parser.add_argument("--force", action="store_true", help="覆盖已有生成器")
    args = parser.parse_args()

    unit = (ROOT / args.unit).resolve()
    try:
        rel = rel_to_root(unit)
    except ValueError:
        print(f"✗ 目标不在仓库内：{args.unit}", file=sys.stderr)
        return 1

    if args.check:
        problems = check(unit, rel)
        if problems:
            for p in problems:
                print(f"✗ {p}")
            return 1
        print(f"✓ {rel}/{GENERATOR} 通过底线检查（断言 / 缓存 / 字体 / images）")
        return 0
    return scaffold(unit, rel, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
