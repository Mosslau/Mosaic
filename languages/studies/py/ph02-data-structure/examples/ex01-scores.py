# 来源：languages/py/ph02-data-structure/02-data-structure.md 第 6 章「示例 1：成绩管理」
# 说明：用 list 管理一组成绩——平均分、排序取前三、及格人数、统一加分（封顶 100）。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 ex01-scores.py
# 验证状态：已验证

"""成绩管理示例：演示 list 的排序、切片与列表推导式。"""


def main() -> None:
    """演示 list 管理成绩的常见操作。"""
    scores = [78, 92, 85, 67, 88, 91, 73]

    # 1. 计算平均分
    average = sum(scores) / len(scores)
    print(f"平均分: {average:.2f}")

    # 2. 排序并取前三名
    ranked = sorted(scores, reverse=True)
    top3 = ranked[:3]
    print(f"前三名: {top3}")

    # 3. 及格人数
    passed = [s for s in scores if s >= 60]
    print(f"及格人数: {len(passed)}")

    # 4. 每个分数加 5 分（最高不超过 100）
    bonus = [min(s + 5, 100) for s in scores]
    print(f"加分后: {bonus}")


if __name__ == "__main__":
    main()
