# project/src/pyproject_template/cli.py —— CLI 主逻辑（argparse，含 --version 与 echo 子命令）
# 来源：Python 项目模板（ph07 阶段项目）
# 验证环境：Python 3.13.12
# 运行：pip install -e . 后 pyproj echo hello；或 python3 -m pyproject_template echo hello
# 验证状态：已验证

"""pyproj 命令入口：演示 argparse 子命令与 --version 的标准写法。"""

import argparse

from pyproject_template import __version__


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器：--version + echo 子命令。"""
    parser = argparse.ArgumentParser(
        prog="pyproj",
        description="Python 项目模板示例 CLI",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    echo_parser = subparsers.add_parser("echo", help="回显一段文本")
    echo_parser.add_argument("text", help="要回显的文本")
    echo_parser.add_argument(
        "--upper", action="store_true", help="转大写后回显"
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """解析参数并分发到子命令处理逻辑。"""
    args = build_parser().parse_args(argv)
    if args.command == "echo":
        text = args.text.upper() if args.upper else args.text
        print(text)


if __name__ == "__main__":
    main()
