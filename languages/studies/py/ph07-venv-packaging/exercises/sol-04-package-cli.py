# exercises/sol-04-package-cli.py —— 练习 4 参考实现：打包 argparse 小工具为可安装 CLI
# 来源：07-venv-packaging.md 第 6 章示例 4 / exercises/README.md 练习 4
# 说明：临时目录生成 src 布局包，pip install -e . → 命令可用 → python -m build 产出 wheel → 新 venv 装 wheel 复验
# 验证环境：Python 3.13.12（macOS / Linux），需联网安装 build
# 运行：python3 sol-04-package-cli.py
# 验证状态：已验证

"""练习 4 参考实现：console_scripts 打包 + 可编辑安装 + wheel 构建与安装验证。"""

import subprocess
import sys
import tempfile
from pathlib import Path

PYPROJECT = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "greet-cli"
version = "0.1.0"
description = "练习 4 参考实现：可安装 CLI"
requires-python = ">=3.10"

[project.scripts]
greet = "greet.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
"""

INIT = '''"""greet —— 练习 4 参考实现包。"""

__version__ = "0.1.0"
'''

CLI = '''"""greet 命令入口：argparse 解析名字并打印问候。"""

import argparse


def main(argv: list[str] | None = None) -> None:
    """解析命令行参数并打印问候语。"""
    parser = argparse.ArgumentParser(description="问候工具")
    parser.add_argument("name", help="要问候的名字")
    args = parser.parse_args(argv)
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
'''

MAIN = '''"""支持 python -m greet 调用。"""

from greet.cli import main

if __name__ == "__main__":
    main()
'''

GITIGNORE = ".venv/\n__pycache__/\n*.pyc\ndist/\nbuild/\n*.egg-info/\n"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """运行命令并返回结果，失败时抛出异常。"""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def main() -> None:
    """生成 src 布局包，验证可编辑安装、python -m 入口、wheel 构建与新环境安装。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pkg = root / "src" / "greet"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(INIT, encoding="utf-8")
        (pkg / "cli.py").write_text(CLI, encoding="utf-8")
        (pkg / "__main__.py").write_text(MAIN, encoding="utf-8")
        (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

        run([sys.executable, "-m", "venv", str(root / ".venv")])
        python = str(root / ".venv" / "bin" / "python")
        greet = str(root / ".venv" / "bin" / "greet")

        # 1. 可编辑安装：生成 greet 命令
        run([python, "-m", "pip", "install", "--quiet", "-e", str(root)])
        out = run([greet, "Alice"]).stdout.strip()
        assert out == "Hello, Alice!", f"console_scripts 输出不符：{out}"
        print(f"pip install -e . 后 greet Alice → {out}")

        # 2. python -m 入口输出一致
        out_m = run([python, "-m", "greet", "Alice"]).stdout.strip()
        assert out_m == out, "python -m 入口输出不一致"
        print(f"python -m greet Alice → {out_m}")

        # 3. 可编辑安装即时生效：改源码不重装
        cli_file = pkg / "cli.py"
        cli_file.write_text(CLI.replace("Hello,", "Hi,"), encoding="utf-8")
        out2 = run([greet, "Alice"]).stdout.strip()
        assert out2 == "Hi, Alice!", "可编辑安装未即时生效"
        print("可编辑安装即时生效验证通过（改源码不重装）")

        # 4. 构建 sdist + wheel
        run([python, "-m", "pip", "install", "--quiet", "build"])
        run([python, "-m", "build", "--outdir", str(root / "dist"), str(root)])
        wheels = list((root / "dist").glob("*.whl"))
        sdists = list((root / "dist").glob("*.tar.gz"))
        assert wheels and sdists, "dist/ 下缺少 wheel 或 sdist"
        print(f"构建产物：{wheels[0].name}、{sdists[0].name}")

        # 5. 全新 venv 安装 wheel 复验
        run([sys.executable, "-m", "venv", str(root / ".venv2")])
        python2 = str(root / ".venv2" / "bin" / "python")
        run([python2, "-m", "pip", "install", "--quiet", str(wheels[0])])
        out3 = run([str(root / ".venv2" / "bin" / "greet"), "Alice"]).stdout.strip()
        assert out3 == "Hi, Alice!", "wheel 安装后命令输出不符"
        print("新 venv 安装 wheel 后 greet Alice → " + out3)

    print("练习 4 验收通过")


if __name__ == "__main__":
    main()
