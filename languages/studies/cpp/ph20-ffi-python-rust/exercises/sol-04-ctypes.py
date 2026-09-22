# sol-04-ctypes.py —— 练习 4 参考实现（Python 侧）
# 验证环境：Python 3.13.12；前置：先编出 /tmp/libsumm.dylib
# 运行：python3 sol-04-ctypes.py（预期断言全绿、退出码 0）
# 验证状态：已验证
# 教学点：字符串跨语言写回 = 调用者缓冲 + cap（零所有权转移）；缓冲太小走错误码不崩；
#         所有内存（含缓冲与句柄）都由 Python 侧分配/回收——库从不 new 跨边界指针。
import ctypes

lib = ctypes.CDLL("/tmp/libsumm.dylib")

TLS_OK, TLS_ERR_NULL, TLS_ERR_SMALL, TLS_ERR_INVALID = 0, 1, 2, 3

lib.tls_summarize.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_long,
    ctypes.c_char_p,
    ctypes.c_long,
]
lib.tls_summarize.restype = ctypes.c_int
lib.tls_version.restype = ctypes.c_int
assert lib.tls_version() >= 1

xs = (ctypes.c_double * 3)(1.0, 2.0, 3.0)

# 正常路径：容量 64 足够 → 写回 "n=3 sum=6.000" 且 NUL 结尾
buf = ctypes.create_string_buffer(64)
rc = lib.tls_summarize(xs, 3, buf, ctypes.sizeof(buf))
assert rc == TLS_OK
assert buf.value == b"n=3 sum=6.000"

# 错误路径 1：cap=0（连 NUL 都放不下）→ 错误码 2
tiny = ctypes.create_string_buffer(1)
assert lib.tls_summarize(xs, 3, tiny, 0) == TLS_ERR_SMALL
# 错误路径 2：xs 为 NULL → 错误码 1
assert lib.tls_summarize(None, 3, buf, ctypes.sizeof(buf)) == TLS_ERR_NULL
# 错误路径 3：n<=0 → 错误码 3
assert lib.tls_summarize(xs, 0, buf, ctypes.sizeof(buf)) == TLS_ERR_INVALID

print("summarize='n=3 sum=6.000' err(cap0)=2 err(NULL)=1 err(n<=0)=3")
print("sol-04 ctypes OK")
