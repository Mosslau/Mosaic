#!/usr/bin/env python3
"""ex03-py-ctypes.py —— Python 用 ctypes 调用 C 动态库 libcalc

运行:
    python3 ex03-py-ctypes.py [/tmp/ph14-ex/libcalc.dylib]
（argv[1] 可换成你自己的动态库路径；不传则用默认构建路径）

验证环境：Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
要点：
    - argtypes / restype 要显式声明：ctypes 默认把整数当 c_int 传，
      与 int32_t 恰好一致，但"显式声明"是跨语言调用的纪律（文档 3.6）
    - 错误码约定：0 成功、负数错误，在 Python 侧同样要检查
    - 字符串用 c_char_p：只读借用，Python 侧负责 bytes 的生命周期
"""
import ctypes
import sys

LIB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ph14-ex/libcalc.dylib"

lib = ctypes.CDLL(LIB)

# 显式声明参数与返回类型（int32_t == c_int32）
lib.calc_add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.calc_add.restype = ctypes.c_int32

lib.calc_div.argtypes = [ctypes.c_int32, ctypes.c_int32,
                         ctypes.POINTER(ctypes.c_int32)]
lib.calc_div.restype = ctypes.c_int

lib.calc_strlen.argtypes = [ctypes.c_char_p]
lib.calc_strlen.restype = ctypes.c_int32

# 1) 整数往返
assert lib.calc_add(20, 22) == 42, "add(20,22) != 42"
assert lib.calc_add(-1, 1) == 0, "add(-1,1) != 0"

# 2) 指针出参：Python 侧分配 c_int32，ctypes.byref 传地址
out = ctypes.c_int32()
rc = lib.calc_div(84, 2, ctypes.byref(out))
assert rc == 0 and out.value == 42, f"div(84,2): rc={rc} out={out.value}"

# 3) 错误码路径：除零返回 -1，而不是崩溃
rc = lib.calc_div(1, 0, ctypes.byref(out))
assert rc == -1, f"div(1,0) 应返回 -1，实际 {rc}"

# 4) 字符串只读借用：bytes 传给 c_char_p
n = lib.calc_strlen(b"hello")
assert n == 5, f"strlen(hello) != 5"

print("py-ctypes: add(20,22)=42 add(-1,1)=0 div(84,2)=rc0/42 "
      "div(1,0)=rc-1 strlen(hello)=5 —— 全部断言通过")
