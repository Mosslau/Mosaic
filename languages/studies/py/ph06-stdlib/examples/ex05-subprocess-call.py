# examples/ex05-subprocess-call.py —— subprocess 调用外部命令并捕获输出（含超时）
# 来源：06-stdlib.md 第 6 章示例 5
# 验证环境：Python 3.13.12
# 运行：python3 ex05-subprocess-call.py
# 验证状态：已验证

"""用 subprocess.run 调用外部命令：捕获输出、处理非零返回码（check=True）、超时保护。"""

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """在临时目录演示三种子进程调用场景。"""
    with tempfile.TemporaryDirectory() as d:
        data = Path(d) / "data.txt"
        data.write_text("1\n2\n3\n", encoding="utf-8")

        result = subprocess.run(                 # 调用系统命令统计行数
            ["wc", "-l", str(data)],
            capture_output=True, text=True, timeout=10,
        )
        print("返回码:", result.returncode)
        print("输出:", result.stdout.strip())

        try:                                     # check=True：非零返回码抛异常
            subprocess.run([sys.executable, "-c", "import sys; sys.exit(2)"],
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"命令返回非零退出码: {e.returncode}")

        try:                                     # 超时保护：防止外部命令卡死脚本
            subprocess.run(["sleep", "30"], timeout=2)
        except subprocess.TimeoutExpired:
            print("命令超过 2 秒未完成，已终止")


if __name__ == "__main__":
    main()
