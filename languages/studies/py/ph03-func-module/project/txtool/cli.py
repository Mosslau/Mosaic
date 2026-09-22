# project/txtool/cli.py —— txtool 主入口：解析 sys.argv，分发子命令
# 验证环境：Python 3.13.12
# 运行：在 project/ 目录下执行 python3 -m txtool <子命令> ...
# 已验证：本环境 wc/grep/head/tail 子命令及 --help 均验证通过

"""txtool 主入口：解析参数并分发子命令。"""
from txtool import files, ops

def print_usage() -> None:
    """打印用法说明。"""
    print("用法: python3 -m txtool <子命令> [参数]")
    print()
    print("子命令:")
    print("  wc <文件>                统计行数/词数/字符数")
    print("  grep <关键词> <文件>     显示包含关键词的行（带行号）")
    print("  head <n> <文件>          显示前 n 行")
    print("  tail <n> <文件>          显示后 n 行")
    print("  -h, --help               显示本帮助")

def cmd_wc(args: list[str]) -> int:
    """wc 子命令：统计行数/词数/字符数。"""
    if len(args) != 1:
        print("wc 需要一个文件参数")
        return 1
    stats = ops.count_stats(files.read_lines(args[0]))
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0

def cmd_grep(args: list[str]) -> int:
    """grep 子命令：过滤包含关键词的行。"""
    if len(args) != 2:
        print("grep 需要 <关键词> <文件> 两个参数")
        return 1
    keyword, path = args
    for line_no, line in ops.filter_lines(files.read_lines(path), keyword):
        print(f"{line_no}: {line}")
    return 0

def cmd_head(args: list[str]) -> int:
    """head 子命令：显示前 n 行。"""
    if len(args) != 2:
        print("head 需要 <n> <文件> 两个参数")
        return 1
    n = _parse_n(args[0])
    if n is None:
        return 1
    for line in ops.take_first(files.read_lines(args[1]), n):
        print(line)
    return 0

def cmd_tail(args: list[str]) -> int:
    """tail 子命令：显示后 n 行。"""
    if len(args) != 2:
        print("tail 需要 <n> <文件> 两个参数")
        return 1
    n = _parse_n(args[0])
    if n is None:
        return 1
    for line in ops.take_last(files.read_lines(args[1]), n):
        print(line)
    return 0

def _parse_n(raw: str) -> int | None:
    """把字符串解析为正整数，失败返回 None。"""
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    print(f"无效的行数: {raw}")
    return None

COMMANDS = {
    "wc": cmd_wc,
    "grep": cmd_grep,
    "head": cmd_head,
    "tail": cmd_tail,
}

def main(argv: list[str]) -> int:
    """解析参数并分发到对应子命令，返回退出码。"""
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print_usage()
        return 0
    cmd = argv[1]
    func = COMMANDS.get(cmd)
    if func is None:
        print(f"未知命令: {cmd}，可用: {list(COMMANDS)}")
        print_usage()
        return 1
    return func(argv[2:])
