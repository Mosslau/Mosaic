# exercises/sol-02-requirements.py —— 练习 2 参考实现：生成 requirements.txt 并全新环境复现
# 来源：07-venv-packaging.md 第 6 章示例 2 / exercises/README.md 练习 2
# 说明：环境 A freeze 出清单 → 全新环境 B 按清单安装 → diff 两个环境的 freeze 输出
# 验证环境：Python 3.13.12（macOS / Linux），需联网安装 requests
# 运行：python3 sol-02-requirements.py
# 验证状态：已验证

"""练习 2 参考实现：pip freeze 快照 + 全新环境一键复现。"""

import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """运行命令并返回结果，失败时抛出异常。"""
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def freeze(python: str) -> str:
    """返回指定解释器环境的 pip freeze 输出。"""
    return run([python, "-m", "pip", "freeze"]).stdout


def main() -> None:
    """环境 A 冻结快照，全新环境 B 复现，对比两个环境的包清单。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        req_file = root / "requirements.txt"

        # ---- 环境 A：安装包后 freeze ----
        run([sys.executable, "-m", "venv", str(root / ".venv-a")])
        python_a = str(root / ".venv-a" / "bin" / "python")
        run([python_a, "-m", "pip", "install", "--quiet", "requests"])
        req_file.write_text(freeze(python_a), encoding="utf-8")
        print("requirements.txt 内容：")
        print(req_file.read_text(encoding="utf-8"))

        # 验收点 1：清单中每行都带精确版本 ==
        for line in req_file.read_text(encoding="utf-8").splitlines():
            assert "==" in line, f"存在未锁定的包：{line}"

        # ---- 环境 B：全新环境按清单复现 ----
        run([sys.executable, "-m", "venv", str(root / ".venv-b")])
        python_b = str(root / ".venv-b" / "bin" / "python")
        run([python_b, "-m", "pip", "install", "--quiet", "-r", str(req_file)])

        # 验收点 2：环境 B 中包可 import
        run([python_b, "-c", "import requests"])

        # 验收点 3：两个环境的 freeze 输出完全一致
        assert freeze(python_a) == freeze(python_b), "两个环境的包清单不一致"
        print("两个环境的 pip freeze 输出完全一致")

    print("练习 2 验收通过")


if __name__ == "__main__":
    main()
