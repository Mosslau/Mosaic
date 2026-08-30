# exercises/sol-01-create-venv.py —— 练习 1 参考实现：创建虚拟环境并验证隔离
# 来源：07-venv-packaging.md 第 6 章示例 1 / exercises/README.md 练习 1
# 说明：用 subprocess 驱动 venv/pip 全流程，断言 sys.prefix 指向虚拟环境
# 验证环境：Python 3.13.12（macOS / Linux），需联网安装 requests
# 运行：python3 sol-01-create-venv.py
# 验证状态：已验证

"""练习 1 参考实现：创建虚拟环境、激活等价物（直接调用 .venv/bin/python）、验证隔离。"""

import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """运行命令并返回结果，失败时抛出异常。"""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def main() -> None:
    """在临时目录创建 venv，验证解释器指向、安装依赖、退出后系统环境隔离。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        venv_dir = root / ".venv"
        venv_python = venv_dir / "bin" / "python"

        # 1. 创建虚拟环境（等价 shell：python3 -m venv .venv）
        run([sys.executable, "-m", "venv", str(venv_dir)])
        assert venv_python.exists(), "虚拟环境解释器不存在"

        # 2. 验证解释器指向 .venv（等价激活后 which python）
        prefix = run([str(venv_python), "-c", "import sys; print(sys.prefix)"]).stdout.strip()
        assert prefix.endswith(".venv"), f"sys.prefix 未指向 .venv：{prefix}"
        print(f"虚拟环境解释器验证通过：sys.prefix = {prefix}")

        # 3. 用该环境的 pip 安装依赖（永远用 python -m pip，不用裸 pip）
        run([str(venv_python), "-m", "pip", "install", "--quiet", "requests"])
        version = run(
            [str(venv_python), "-c", "import requests; print(requests.__version__)"]
        ).stdout.strip()
        print(f"虚拟环境内 requests 安装成功：{version}")

        # 4. 验证隔离：系统 python3 的 sys.prefix 不指向 .venv
        sys_prefix = run(
            [sys.executable, "-c", "import sys; print(sys.prefix)"]
        ).stdout.strip()
        assert not sys_prefix.endswith(".venv"), "系统环境被污染"
        assert sys_prefix != prefix, "两个环境的 sys.prefix 不应相同"
        print(f"隔离验证通过：系统 sys.prefix = {sys_prefix}")

    print("练习 1 验收通过")


if __name__ == "__main__":
    main()
