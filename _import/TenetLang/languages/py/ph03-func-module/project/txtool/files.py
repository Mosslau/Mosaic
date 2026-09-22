# project/txtool/files.py —— 文件读写封装
# 验证环境：Python 3.13.12
# 运行：通过 python3 -m txtool 各子命令调用
# 已验证：本环境经 wc/grep/head/tail 子命令验证

"""文件读写封装函数集合。"""

def read_lines(path: str) -> list[str]:
    """读取文件，返回去掉换行符的行列表。"""
    with open(path, encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]
