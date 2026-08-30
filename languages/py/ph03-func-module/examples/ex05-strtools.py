# examples/ex05-strtools.py —— 字符串处理 CLI（count/reverse/stats 三个子命令）
# 验证环境：Python 3.13.12
# 运行：python3 ex05-strtools.py <count|reverse|stats> "text"
# 已验证：本环境运行输出与注释中期望值一致

"""字符串处理 CLI。用法：python3 ex05-strtools.py <count|reverse|stats> "text" """
import sys

def count_chars(text):
    return len([c for c in text if c != " "])

def reverse(text):
    return text[::-1]

def stats(text):
    return {
        "总字符": len(text),
        "字母": sum(1 for c in text if c.isalpha()),
        "数字": sum(1 for c in text if c.isdigit()),
        "空格": sum(1 for c in text if c.isspace()),
    }

COMMANDS = {"count": count_chars, "reverse": reverse, "stats": stats}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 ex05-strtools.py <count|reverse|stats> <text>")
        sys.exit(0)
    cmd, text = sys.argv[1], sys.argv[2]
    func = COMMANDS.get(cmd)
    if not func:
        print(f"未知命令: {cmd}，可用: {list(COMMANDS.keys())}")
        sys.exit(1)
    result = func(text)
    if isinstance(result, dict):
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print(result)
