# 来源：languages/py/ph02-data-structure/exercises/README.md 练习 1「list 管理成绩」
# 说明：参考实现——平均分、最高/最低分、降序前三名、及格人数统计。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 sol-01-scores.py
# 验证状态：已验证

"""练习 1 参考实现：用 list 管理成绩。"""


def main() -> None:
    """对给定成绩列表做统计分析。"""
    scores = [78, 92, 85, 67, 88, 91, 73]

    average = sum(scores) / len(scores)
    print(f"平均分: {average:.2f}")
    print(f"最高分: {max(scores)}")
    print(f"最低分: {min(scores)}")

    top3 = sorted(scores, reverse=True)[:3]
    print(f"前三名: {top3}")

    passed = [s for s in scores if s >= 60]
    print(f"及格人数: {len(passed)}")


if __name__ == "__main__":
    main()
