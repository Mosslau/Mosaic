# 来源：languages/py/ph02-data-structure/02-data-structure.md 第 6 章「示例 5：读取多行输入并分组」
# 说明：读取标准输入的「姓名 分数」行，按分数段分组到 dict of list，直到 EOF。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：printf 'Alice 85\nBob 92\nCarol 78\nDave 55\n' | python3 ex05-group-input.py
# 验证状态：已验证

"""输入分组示例：演示 dict of list 与按条件分组。"""

import sys


def main() -> None:
    """从标准输入读取「姓名 分数」行并按分数段分组。"""
    groups = {"优秀": [], "良好": [], "及格": [], "不及格": []}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        name, score_str = line.split()
        score = int(score_str)
        if score >= 90:
            groups["优秀"].append(name)
        elif score >= 80:
            groups["良好"].append(name)
        elif score >= 60:
            groups["及格"].append(name)
        else:
            groups["不及格"].append(name)

    for level, names in groups.items():
        print(f"{level}: {names}")


if __name__ == "__main__":
    main()
