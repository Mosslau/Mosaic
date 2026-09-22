# exercises/sol-03-file-tools/main.py —— 文件统计入口脚本参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main.py <文件路径>
# 已验证：本环境运行输出与期望一致

"""读取文本文件并打印统计信息。"""
import sys

import file_tools

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 main.py <文件路径>")
        sys.exit(1)
    target = sys.argv[1]
    print(f"文件: {target}")
    print(f"行数: {file_tools.count_lines(target)}")
    print(f"词数: {file_tools.count_words(target)}")
