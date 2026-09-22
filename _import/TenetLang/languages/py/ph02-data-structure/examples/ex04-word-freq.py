# 来源：languages/py/ph02-data-structure/02-data-structure.md 第 6 章「示例 4：词频统计」
# 说明：用 dict.get 统计词频、sorted 按频率降序、set 差集去掉停用词。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 ex04-word-freq.py
# 验证状态：已验证

"""词频统计示例：演示 dict 计数、按值排序与 set 去重。"""


def main() -> None:
    """统计一段文本的词频并按频率降序输出。"""
    text = "apple banana apple orange banana apple"
    words = text.split()

    # 统计词频：get(w, 0) 在词首次出现时给默认计数 0
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # 按频率降序输出
    for word, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        print(f"{word}: {count}")

    # 使用 set 去重停用词
    stopwords = {"the", "a", "is"}
    unique_words = set(words)
    print(f"不重复词数: {len(unique_words - stopwords)}")


if __name__ == "__main__":
    main()
