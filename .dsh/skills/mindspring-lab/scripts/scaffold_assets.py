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

# 中文字体：按字体名查 + FreeType 字形校验，找不到就直接报错，避免图里出现"方块"。
# 为什么不用「硬编码 Linux 字体路径 + exists()」：那个写法在 macOS / Windows 上一个
# 候选都命不中，循环静默跳过 → font.family 保持默认 DejaVu Sans（无中文字形）→
# 整张图中文变方框，而 matplotlib 只在 stderr 发 UserWarning、退出码仍是 0。
def setup_cjk_font() -> str:
    cjk_names = (
        "Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",           # Linux
        "Hiragino Sans GB", "PingFang SC", "Heiti TC",
        "STHeiti", "Songti SC", "Arial Unicode MS",           # macOS
        "Microsoft YaHei", "SimHei",                          # Windows
    )
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)

    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in cjk_names if n in available), None)
    if chosen is None:
        raise SystemExit(
            "找不到含中文字形的字体，拒绝生成方块版素材。\\n"
            f"fontManager 已扫描到 {len(available)} 个字体族，但无候选命中。\\n"
            "请安装任一中文字体（如 Noto Sans CJK / 文泉驿）后重跑。"
        )

    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font

    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen}（{font_path}）不含中文字形，拒绝生成方块版素材")

    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False  # 负号走 ASCII，避免 U+2212 缺字形
    return chosen


FONT_USED = setup_cjk_font()

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


CHILD_PROBE = r'''
import ast, sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding="utf-8")
tree = ast.parse(src)
fn = next((n for n in tree.body
           if isinstance(n, ast.FunctionDef) and n.name == "setup_cjk_font"), None)
if fn is None:
    print("NOCALL 生成器里没有 setup_cjk_font()——无法确认中文字体是否真的注册成功")
    sys.exit(0)

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 只执行字体解析函数本身，不跑生成器的其它副作用（不写图、不建目录）
ns = {"Path": Path, "font_manager": font_manager, "plt": plt, "__name__": "_probe"}
try:
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<probe>", "exec"), ns)
    print("OK", ns["setup_cjk_font"]())
except SystemExit as e:
    print("FAIL", e)
'''


def runtime_font_probe(path: Path) -> tuple[str, str]:
    """真的把生成器的字体解析跑一遍，返回 (状态, 详情)。

    为什么不能只 grep 关键字：`if "font_manager" in src` 在脚本 import 了
    font_manager、却一个中文字体都没注册成功时照样通过——图里全是方块，检查
    却报"✓ 通过"。本函数用 AST 抽出 setup_cjk_font()（或调用它的语句）实际执行，
    并把结果与真实的 fontManager 对照，只有拿到含「中」字形的字体名才算通过。
    """
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, "-c", CHILD_PROBE, str(path)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "FAIL", "字体探测超时（>120s）"

    out = (proc.stdout or "").strip().splitlines()
    verdict = out[-1] if out else ""
    if verdict.startswith("OK "):
        name = verdict[3:].strip()
        if not name:
            return "FAIL", "setup_cjk_font() 返回空字体名"
        return "OK", name
    if verdict.startswith("FAIL "):
        return "FAIL", verdict[5:].strip().replace("\n", " ")
    if verdict.startswith("NOCALL"):
        return "NOCALL", verdict[7:].strip()
    return "FAIL", (proc.stderr or "").strip().splitlines()[-1] if proc.stderr else "探测无输出"


def check(unit: Path, rel: str) -> list[str]:
    """检查已存在的生成器是否具备底线要素。

    字体一项按**运行时结果**判定，不按关键字：见 runtime_font_probe。
    """
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
    else:
        status, detail = runtime_font_probe(path)
        if status == "FAIL":
            problems.append(
                f"{rel}/{GENERATOR}：中文字体解析失败——图里会出现方块（{detail}）"
            )
        elif status == "NOCALL":
            problems.append(
                f"{rel}/{GENERATOR}：有 font_manager 但没有 setup_cjk_font()，"
                "无法确认真实注册了中文字体——建议改用脚手架模板的写法"
            )
    if "unicode_minus" not in src:
        problems.append(
            f"{rel}/{GENERATOR}：未设 axes.unicode_minus=False——带负值的图里负号会变方块"
        )
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
