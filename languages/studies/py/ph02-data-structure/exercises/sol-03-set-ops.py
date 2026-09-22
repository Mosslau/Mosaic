# 来源：languages/py/ph02-data-structure/exercises/README.md 练习 3「set 去重与集合运算」
# 说明：参考实现——列表去重计数，交集、并集、差集运算。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 sol-03-set-ops.py
# 验证状态：已验证

"""练习 3 参考实现：set 去重与集合运算。"""


def main() -> None:
    """演示 set 去重与交并差运算。"""
    words = ["apple", "banana", "apple", "orange", "banana"]
    unique_words = set(words)
    print(f"去重后: {unique_words}")
    print(f"不重复单词数: {len(unique_words)}")

    a = {"red", "green", "blue"}
    b = {"green", "blue", "yellow"}
    print(f"交集: {a & b}")
    print(f"并集: {a | b}")
    print(f"a 独有: {a - b}")


if __name__ == "__main__":
    main()
