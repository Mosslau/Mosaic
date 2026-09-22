# exercises/sol-03-pyproject.py —— 练习 3 参考实现：用 pyproject.toml 管理项目
# 来源：07-venv-packaging.md 第 6 章示例 3 / exercises/README.md 练习 3
# 说明：临时目录生成包 + pyproject.toml（运行依赖 + dev 分组），pip install -e ".[dev]" 后断言
# 验证环境：Python 3.13.12（macOS / Linux），需联网安装 pytest（dev 分组）
# 运行：python3 sol-03-pyproject.py
# 验证状态：已验证

"""练习 3 参考实现：PEP 621 元数据 + optional-dependencies 分组，可编辑安装后验证。"""

import subprocess
import sys
import tempfile
from pathlib import Path

PYPROJECT = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "sol3-demo"
version = "0.1.0"
description = "练习 3 参考实现包"
requires-python = ">=3.10"
dependencies = []                     # 本练习不引第三方运行依赖，聚焦分组机制

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
where = ["src"]
"""

INIT = '''"""sol3_demo —— 练习 3 参考实现包。"""

__version__ = "0.1.0"
'''


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """运行命令并返回结果，失败时抛出异常。"""
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main() -> None:
    """生成包骨架 + pyproject.toml，pip install -e ".[dev]" 后验证 import 与 dev 分组。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pkg = root / "src" / "sol3_demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(INIT, encoding="utf-8")
        (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")

        run([sys.executable, "-m", "venv", str(root / ".venv")])
        python = str(root / ".venv" / "bin" / "python")

        # 1. 可编辑安装（运行依赖 + dev 分组一次装齐）
        run([python, "-m", "pip", "install", "--quiet", "-e", f"{root}[dev]"])

        # 2. 验证包可 import 且版本正确
        version = run(
            [python, "-c", "import sol3_demo; print(sol3_demo.__version__)"]
        ).stdout.strip()
        assert version == "0.1.0", f"版本不符：{version}"
        print(f"import sol3_demo 成功，版本 {version}")

        # 3. 验证 dev 分组的包（pytest）已安装
        show = run([python, "-m", "pip", "show", "pytest"]).stdout
        assert "Name: pytest" in show, "dev 分组的 pytest 未安装"
        print("dev 分组验证通过：pytest 已随 .[dev] 安装")

        # 4. 验证元数据可被 pip 读取（PEP 621 生效）
        meta = run([python, "-m", "pip", "show", "sol3-demo"]).stdout
        assert "Version: 0.1.0" in meta, "PEP 621 元数据未生效"
        print("PEP 621 元数据验证通过（pip show 可读到 name/version）")

    print("练习 3 验收通过")


if __name__ == "__main__":
    main()
