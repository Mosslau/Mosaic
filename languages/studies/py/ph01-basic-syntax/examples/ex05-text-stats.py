# examples/ex05-text-stats.py —— 文本统计：从 stdin 读文本，输出字符/单词/行数
# 验证环境：Python 3.13.12（macOS）
# 运行：echo "hello world" | python3 ex05-text-stats.py
# 验证状态：已验证

import sys


def count_chars(text):
    """统计字符数（含空格）"""
    return len(text)


def count_words(text):
    """统计单词数"""
    return len(text.split())


def count_lines(text):
    """统计行数"""
    return text.count('\n') + 1


if __name__ == "__main__":
    text = sys.stdin.read()
    print(f"字符数: {count_chars(text)}")
    print(f"单词数: {count_words(text)}")
    print(f"行数:   {count_lines(text)}")
