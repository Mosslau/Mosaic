# examples/ex04-hello-cli/src/hello/__main__.py —— python -m hello 入口
# 来源：07-venv-packaging.md 第 6 章示例 4（src 布局补全）
# 验证环境：Python 3.13.12
# 运行：python3 -m hello Alice（包已安装或 PYTHONPATH=src 时）
# 验证状态：已验证

"""支持 `python -m hello` 调用，转发到 cli.main。"""

from hello.cli import main

if __name__ == "__main__":
    main()
