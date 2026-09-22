# 来源：languages/py/ph02-data-structure/exercises/README.md 练习 4「统计词频」
# 说明：参考实现——dict 计数、按频率降序输出、不重复词总数。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 sol-04-word-freq.py
# 验证状态：已验证

"""练习 4 参考实现：统计词频。"""


def main() -> None:
    """统计文本中每个单词的出现次数并降序输出。"""
    text = "apple banana apple orange banana apple"
    words = text.split()

    freq = {}
    for word in words:
        freq[word] = freq.get(word, 0) + 1

    for word, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        print(f"{word}: {count}")

    print(f"不重复词数: {len(freq)}")


if __name__ == "__main__":
    main()
