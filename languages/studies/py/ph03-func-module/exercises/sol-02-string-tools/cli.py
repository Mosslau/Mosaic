# exercises/sol-02-string-tools/cli.py —— 字符串工具 CLI 参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 cli.py <reverse|stats|upper|lower> "文本"
# 已验证：本环境运行输出与期望一致

"""字符串处理 CLI。"""
import sys

import string_tools

COMMANDS = {
    "reverse": string_tools.reverse,
    "stats": string_tools.char_stats,
    "upper": string_tools.to_upper,
    "lower": string_tools.to_lower,
}

def print_usage() -> None:
    """打印用法说明。"""
    print("用法: python3 cli.py <reverse|stats|upper|lower> <文本>")

def main(argv: list[str]) -> int:
    """解析参数并执行对应命令，返回退出码。"""
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        print_usage()
        return 0
    cmd, text = argv[1], argv[2]
    func = COMMANDS.get(cmd)
    if func is None:
        print(f"未知命令: {cmd}，可用: {list(COMMANDS)}")
        return 1
    result = func(text)
    if isinstance(result, dict):
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print(result)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
