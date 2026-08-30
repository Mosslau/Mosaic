# exercises/sol-03-file-tools/file_tools.py —— 文件读写封装参考实现
# 验证环境：Python 3.13.12
# 运行：直接运行 python3 file_tools.py <文件路径> 做统计
# 已验证：本环境运行输出与期望一致

"""文件读写封装函数集合。"""

def read_lines(path: str) -> list[str]:
    """读取文件，返回去掉换行符的行列表。"""
    with open(path, encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]

def write_lines(path: str, lines: list[str]) -> None:
    """把行列表写入文件，每行追加换行符。"""
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

def count_words(path: str) -> int:
    """统计文件的词数（按空白切分）。"""
    total = 0
    for line in read_lines(path):
        total += len(line.split())
    return total

def count_lines(path: str) -> int:
    """统计文件的行数。"""
    return len(read_lines(path))

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python3 file_tools.py <文件路径>")
        sys.exit(1)
    target = sys.argv[1]
    print(f"行数: {count_lines(target)}")
    print(f"词数: {count_words(target)}")
