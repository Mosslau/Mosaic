#!/usr/bin/env python3
"""py_kvdb.py —— Python ctypes 调用 kvdb C ABI 库
（roadmap 推荐项目「Python 调用 C buffer 解析库」+「C ABI KV 插件接口」）

运行:
    python3 py_kvdb.py [/tmp/ph14-proj/libkvdb.dylib] [/tmp/ph14-proj/py-test.db]
（argv[1]/[2] 可换成你自己的库路径与 WAL 路径）

验证环境: Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
验证状态: 已验证（全部断言通过, 退出码 0; 实测输出见文件尾）
要点:
    - opaque 句柄: c_void_p 传递, 不拆解内部布局
    - get 走"调用方分配缓冲区"约定: Python 侧 create_string_buffer /
      c_ubyte 数组, C 只写; 二进制值（含 \0）也能正确往返
    - 错误码: err_out 出参(byref) + kvdb_strerror 读消息
    - WAL 持久化: sync → destroy → 重新 create 后数据仍在（回放）
"""
import ctypes
import os
import sys

LIB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ph14-proj/libkvdb.dylib"
WAL = sys.argv[2] if len(sys.argv) > 2 else "/tmp/ph14-proj/py-test.db"
if os.path.exists(WAL):
    os.unlink(WAL)

lib = ctypes.CDLL(LIB)

lib.kvdb_create.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int32)]
lib.kvdb_create.restype = ctypes.c_void_p
lib.kvdb_put.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
                         ctypes.c_uint32]
lib.kvdb_put.restype = ctypes.c_int32
lib.kvdb_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
                         ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
lib.kvdb_get.restype = ctypes.c_int32
lib.kvdb_sync.argtypes = [ctypes.c_void_p]
lib.kvdb_sync.restype = ctypes.c_int32
lib.kvdb_destroy.argtypes = [ctypes.c_void_p]
lib.kvdb_destroy.restype = ctypes.c_int32
lib.kvdb_strerror.argtypes = [ctypes.c_int32]
lib.kvdb_strerror.restype = ctypes.c_char_p


def errmsg(rc: int) -> str:
    return lib.kvdb_strerror(rc).decode()


err = ctypes.c_int32()
db = lib.kvdb_create(WAL.encode(), ctypes.byref(err))
assert db, f"kvdb_create 失败: {errmsg(err.value)}"
print("py: kvdb_create ok（新建 WAL）")

# put 文本值（c_char_p 传字符串）
assert lib.kvdb_put(db, b"greeting", ctypes.c_char_p(b"hello world"), 11) == 0

# put 二进制值（含 \0）—— c_void_p 参数用 ctypes.cast 显式转指针
raw = (ctypes.c_ubyte * 4)(0x01, 0x00, 0xFF, 0x02)
assert lib.kvdb_put(db, b"blob", ctypes.cast(raw, ctypes.c_void_p), 4) == 0

# get 文本（调用方分配缓冲区）
buf = ctypes.create_string_buffer(64)
vlen = ctypes.c_uint32()
assert lib.kvdb_get(db, b"greeting", buf, len(buf), ctypes.byref(vlen)) == 0
assert buf.raw[:vlen.value] == b"hello world"
print(f"py: get greeting -> {buf.raw[:vlen.value].decode()!r} (len={vlen.value})")

# get 二进制
out = (ctypes.c_ubyte * 4)()
vlen2 = ctypes.c_uint32()
assert lib.kvdb_get(db, b"blob", out, 4, ctypes.byref(vlen2)) == 0
assert bytes(out) == bytes(raw)
print("py: get blob -> 二进制往返一致（含 \\0 字节）")

# NOTFOUND: 错误码 + 错误消息
rc = lib.kvdb_get(db, b"missing", buf, len(buf), ctypes.byref(vlen))
assert rc == -5, f"应返回 -5(NOTFOUND)，实际 {rc}"
print(f"py: get missing -> rc={rc} msg={errmsg(rc)}")

# sync → destroy → 重开: WAL 回放验证持久化
assert lib.kvdb_sync(db) == 0
assert lib.kvdb_destroy(db) == 0
db2 = lib.kvdb_create(WAL.encode(), ctypes.byref(err))
assert db2, f"重开失败: {errmsg(err.value)}"
buf3 = ctypes.create_string_buffer(64)
vlen3 = ctypes.c_uint32()
assert lib.kvdb_get(db2, b"greeting", buf3, len(buf3), ctypes.byref(vlen3)) == 0
assert buf3.raw[:vlen3.value] == b"hello world"
print("py: 重开库后 get(greeting) 仍命中 —— WAL 回放持久化验证通过")
assert lib.kvdb_destroy(db2) == 0
print("py-kvdb: 全部断言通过")

# 实测输出（本机一次运行）：
# py: kvdb_create ok（新建 WAL）
# py: get greeting -> 'hello world' (len=11)
# py: get blob -> 二进制往返一致（含 \0 字节）
# py: get missing -> rc=-5 msg=key not found
# py: 重开库后 get(greeting) 仍命中 —— WAL 回放持久化验证通过
# py-kvdb: 全部断言通过
