#!/usr/bin/env python3
"""sol-01-py-ctypes.py —— 参考实现: 编译一个 C 动态库给 Python 调用

自包含脚本：把题面要求的 C 库（闰年判断）写入 /tmp，用 cc 编译成
动态库，再用 ctypes 调用并断言 4 个用例。先自己做，做完再对照。

前置: 需要 cc（Apple clang / gcc 均可）
运行: python3 sol-01-py-ctypes.py
验证环境: Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
验证状态: 已验证（C 编译零警告; 4 条断言全过, 退出码 0; 实测输出见文件尾）
"""
import ctypes
import subprocess
import sys
import tempfile

# 题面要求的 C 库（等价实现; 你也可以写自己的版本再替换这里的 C_SRC）
C_SRC = r"""
#include <stdint.h>

/* 1 = 闰年, 0 = 非闰年, -1 = 非法参数(year <= 0) */
int32_t leap_is_leap(int32_t year) {
    if (year <= 0)
        return -1;
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}
"""

def main() -> int:
    tmp = tempfile.mkdtemp(prefix="ph14-sol01-")
    c_path = f"{tmp}/leap.c"
    dylib = f"{tmp}/libleap.dylib"
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(C_SRC)

    # 1. 编译动态库（-Wall -Wextra -std=c11 零警告是纪律）
    proc = subprocess.run(
        ["cc", "-Wall", "-Wextra", "-std=c11", "-dynamiclib", c_path,
         "-o", dylib],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print("cc 编译失败:\n" + proc.stderr, file=sys.stderr)
        return 1

    # 2. ctypes 加载并显式声明 argtypes/restype（不要依赖默认 c_int 猜测）
    lib = ctypes.CDLL(dylib)
    lib.leap_is_leap.argtypes = [ctypes.c_int32]
    lib.leap_is_leap.restype = ctypes.c_int32

    # 3. 断言 4 个用例（含非法输入的错误路径）
    cases = [(2000, 1), (1900, 0), (2024, 1), (0, -1)]
    for year, want in cases:
        got = lib.leap_is_leap(year)
        assert got == want, f"leap_is_leap({year}) = {got}, 期望 {want}"
        print(f"leap_is_leap({year}) = {got}（期望 {want}）—— 通过")
    print("sol-01: 全部断言通过, 退出码 0")
    return 0

if __name__ == "__main__":
    sys.exit(main())

# 实测输出（本机一次运行）：
# leap_is_leap(2000) = 1（期望 1）—— 通过
# leap_is_leap(1900) = 0（期望 0）—— 通过
# leap_is_leap(2024) = 1（期望 1）—— 通过
# leap_is_leap(0) = -1（期望 -1）—— 通过
# sol-01: 全部断言通过, 退出码 0
