# examples/ex03-word-count.py —— 词频统计：统计字符串中每个单词出现次数
# 验证环境：Python 3.13.12（macOS）
# 运行：python3 ex03-word-count.py
# 验证状态：已验证

text = "apple banana apple orange banana apple"
words = text.split()

freq = {}
for w in words:
    freq[w] = freq.get(w, 0) + 1    # dict.get 提供默认值

for word, count in sorted(freq.items()):
    print(f"{word}: {count}")
