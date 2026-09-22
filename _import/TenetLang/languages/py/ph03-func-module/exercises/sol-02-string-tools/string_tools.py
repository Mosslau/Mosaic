# exercises/sol-02-string-tools/string_tools.py —— 字符串工具模块参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 cli.py <reverse|stats|upper|lower> "文本"
# 已验证：本环境运行输出与期望一致

"""字符串处理函数集合。"""

def reverse(text: str) -> str:
    """反转字符串。"""
    return text[::-1]

def char_stats(text: str) -> dict[str, int]:
    """统计字符数：总字符/字母/数字/空格。"""
    return {
        "总字符": len(text),
        "字母": sum(1 for c in text if c.isalpha()),
        "数字": sum(1 for c in text if c.isdigit()),
        "空格": sum(1 for c in text if c.isspace()),
    }

def to_upper(text: str) -> str:
    """转大写。"""
    return text.upper()

def to_lower(text: str) -> str:
    """转小写。"""
    return text.lower()
