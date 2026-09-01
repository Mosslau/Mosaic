#!/usr/bin/env python3
"""ex05-py-handle.py —— Python ctypes 调用 session 句柄库
（opaque pointer + create/destroy + 错误码/错误消息）

运行:
    python3 ex05-py-handle.py [/tmp/ph14-ex/libsession.dylib]
（argv[1] 可换成你自己的动态库路径；不传则用默认构建路径）

验证环境：Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
要点：
    - opaque 句柄在 Python 侧就是 c_void_p：不拆解、不关心内部布局
    - 错误码通过 err_out 出参读取（byref 传 c_int），消息经
      session_strerror 读回（c_char_p，借用）
    - "谁 create 谁 destroy"：Python 侧只负责调用 session_destroy，
      不碰句柄内部的内存
"""
import ctypes
import sys

LIB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ph14-ex/libsession.dylib"
lib = ctypes.CDLL(LIB)

# opaque 句柄：一律用 c_void_p 传递
lib.session_create.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
lib.session_create.restype = ctypes.c_void_p

lib.session_name.argtypes = [ctypes.c_void_p]
lib.session_name.restype = ctypes.c_char_p

lib.session_add.argtypes = [ctypes.c_void_p, ctypes.c_int32]
lib.session_add.restype = ctypes.c_int

lib.session_total.argtypes = [ctypes.c_void_p]
lib.session_total.restype = ctypes.c_int64

lib.session_destroy.argtypes = [ctypes.c_void_p]
lib.session_destroy.restype = ctypes.c_int

lib.session_strerror.argtypes = [ctypes.c_int]
lib.session_strerror.restype = ctypes.c_char_p

err = ctypes.c_int()
s = lib.session_create(b"py-caller", ctypes.byref(err))
assert s, f"create 失败: {lib.session_strerror(err.value).decode()}"
print(f"py: create 成功 name={lib.session_name(s).decode()}")

assert lib.session_add(s, 40) == 0
assert lib.session_add(s, 2) == 0
print(f"py: total={lib.session_total(s)}")

rc = lib.session_destroy(s)                     # 谁 create 谁 destroy
print(f"py: destroy rc={rc} msg={lib.session_strerror(rc).decode()}")

# 错误路径：空 name → NULL + 错误码 -1(BADARG) + 错误消息
bad = lib.session_create(b"", ctypes.byref(err))
assert not bad, "空 name 应返回 NULL"
assert err.value == -1, f"错误码应为 -1(BADARG)，实际 {err.value}"
print(f"py: 空 name → NULL, err={err.value} "
      f"msg={lib.session_strerror(err.value).decode()}")
