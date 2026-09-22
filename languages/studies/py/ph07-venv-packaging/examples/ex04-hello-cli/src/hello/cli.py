# examples/ex04-hello-cli/src/hello/cli.py —— CLI 主逻辑（argparse）
# 来源：07-venv-packaging.md 第 6 章示例 4
# 验证环境：Python 3.13.12
# 运行：pip install -e . 后 hello Alice；或不安装直接 python3 -m hello Alice（需在 src/ 下）
# 验证状态：已验证

"""hello 命令的入口函数：接收一个名字并打印问候语。"""

import argparse


def main(argv: list[str] | None = None) -> None:
    """解析命令行参数并打印问候语；argv 为 None 时取 sys.argv。"""
    parser = argparse.ArgumentParser(description="示例 CLI")
    parser.add_argument("name", help="要问候的名字")
    args = parser.parse_args(argv)
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
