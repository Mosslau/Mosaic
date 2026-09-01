#!/usr/bin/env python3
"""ex06-py-ownership.py —— Python ctypes 消费三种跨语言所有权约定

运行:
    python3 ex06-py-ownership.py [/tmp/ph14-ex/libbufio.dylib]
（argv[1] 可换成你自己的动态库路径；不传则用默认构建路径）

验证环境：Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
要点：
    - 约定 1：C 分配的内存，Python 侧必须调 bufio_str_free 释放，
      绝不能交给 Python 的 GC（ctypes 不会自动 free C 内存）
    - 约定 2：缓冲区由 Python 分配（create_string_buffer），C 只写
    - 约定 3：数组由 Python 分配，C 只读借用
    - 结构体：ctypes.Structure 的字段顺序与宽度必须和 C 结构体一致
"""
import ctypes
import sys

LIB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ph14-ex/libbufio.dylib"
lib = ctypes.CDLL(LIB)

lib.bufio_str_dup.argtypes = [ctypes.c_char_p]
lib.bufio_str_dup.restype = ctypes.c_void_p     # 只当不透明指针收下
lib.bufio_str_free.argtypes = [ctypes.c_void_p]

lib.bufio_str_copy.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                               ctypes.c_char_p]
lib.bufio_str_copy.restype = ctypes.c_size_t

lib.bufio_sum.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t]
lib.bufio_sum.restype = ctypes.c_int64


class BufioPt(ctypes.Structure):                # 与 C 的 bufio_pt 布局一致
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]


lib.bufio_pt_add.argtypes = [BufioPt, BufioPt]
lib.bufio_pt_add.restype = BufioPt

# 约定 1：C 分配 → 用完必须调 bufio_str_free（释放回到 C 侧）
p = lib.bufio_str_dup(b"malloc'd by C")
assert p, "bufio_str_dup 返回 NULL"
content = ctypes.string_at(p)                   # 只读查看内容（借用）
print(f"py 约定1: dup={content.decode()}")
lib.bufio_str_free(p)

# 约定 2：Python 分配缓冲区，C 只写
buf = ctypes.create_string_buffer(32)
need = lib.bufio_str_copy(buf, len(buf), b"caller buffer")
assert buf.value == b"caller buffer", f"实际 {buf.value!r}"
print(f"py 约定2: buf={buf.value.decode()} need={need}")

# 约定 3：C 只读借用 Python 数组
arr = (ctypes.c_int32 * 5)(1, 2, 3, 4, 5)
total = lib.bufio_sum(arr, 5)
assert total == 15, f"sum != 15"
print(f"py 约定3: sum={total}")

# 结构体按值传递（布局一致才能正确解码）
a = BufioPt(10, 20)
b = BufioPt(30, 40)
r = lib.bufio_pt_add(a, b)
assert (r.x, r.y) == (40, 60), f"实际 ({r.x},{r.y})"
print(f"py struct: ({a.x},{a.y})+({b.x},{b.y})=({r.x},{r.y})")
