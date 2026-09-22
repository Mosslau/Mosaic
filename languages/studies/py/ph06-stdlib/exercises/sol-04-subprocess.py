# exercises/sol-04-subprocess.py —— 练习 4 参考实现：subprocess 调命令（捕获输出/非零码/超时）
# 来源：06-stdlib.md 第 7 章「动手练习」练习 4
# 验证环境：Python 3.13.12
# 运行：python3 sol-04-subprocess.py
# 验证状态：已验证

"""调用外部命令并捕获输出；处理非零返回码（check=True）与超时（timeout），全程传参数列表。"""

import subprocess
import sys
import tempfile
from pathlib import Path


def count_lines(path: str) -> str:
    """调用系统 wc -l 统计行数，返回去掉首尾空白的输出；失败时抛 RuntimeError。"""
    result = subprocess.run(                 # 传参数列表，不拼 shell 字符串
        ["wc", "-l", path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"wc 失败: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    """在临时目录演示三种子进程调用场景。"""
    with tempfile.TemporaryDirectory() as d:
        data = Path(d) / "data.txt"
        data.write_text("1\n2\n3\n", encoding="utf-8")

        output = count_lines(str(data))
        print(f"行数统计: {output}（返回码 0）")

        try:                                 # check=True：非零返回码抛异常
            subprocess.run([sys.executable, "-c", "import sys; sys.exit(2)"],
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"非零返回码已被捕获: {e.returncode}")

        try:                                 # 超时保护：防止外部命令卡死脚本
            subprocess.run(["sleep", "5"], timeout=1)
        except subprocess.TimeoutExpired:
            print("命令超时, 已被终止")


if __name__ == "__main__":
    main()
