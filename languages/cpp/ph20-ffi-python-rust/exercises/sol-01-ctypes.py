# sol-01-ctypes.py —— 练习 1 参考实现（Python 侧）
# 验证环境：Python 3.13.12；前置：先按 sol-01-series-lib.cpp 文件头编出 /tmp/libseries.dylib
# 运行：python3 sol-01-ctypes.py（预期断言全绿、退出码 0）
# 验证状态：已验证
# 教学点：数值数组用 (ctypes.c_double * n)() 构造、out 用 byref 传；
#         「指针 + 长度」是容器跨语言唯一安全形态；错误路径逐一断言。
import ctypes
import math

lib = ctypes.CDLL("/tmp/libseries.dylib")

TSLIB_OK, TSLIB_ERR_NULL, TSLIB_ERR_INVALID = 0, 1, 2

# 声明签名：数组参数退化成 c_void_p 也可，但用 POINTER 更精确；统一 restype=c_int
lib.tslib_sum.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.POINTER(ctypes.c_double)]
lib.tslib_sum.restype = ctypes.c_int
lib.tslib_norm2.argtypes = lib.tslib_sum.argtypes
lib.tslib_norm2.restype = ctypes.c_int
lib.tslib_max.argtypes = lib.tslib_sum.argtypes
lib.tslib_max.restype = ctypes.c_int
lib.tslib_version.restype = ctypes.c_int

assert lib.tslib_version() >= 1

# 正常路径：{1,2,3,4}
xs = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
out = ctypes.c_double()
assert lib.tslib_sum(xs, 4, ctypes.byref(out)) == TSLIB_OK and out.value == 10.0
assert lib.tslib_norm2(xs, 4, ctypes.byref(out)) == TSLIB_OK and abs(out.value - math.sqrt(30.0)) < 1e-12
assert lib.tslib_max(xs, 4, ctypes.byref(out)) == TSLIB_OK and out.value == 4.0

# 错误路径 1：xs 为 NULL（None 传给 POINTER）→ 错误码 1
assert lib.tslib_sum(None, 4, ctypes.byref(out)) == TSLIB_ERR_NULL
# 错误路径 2：n <= 0 → 错误码 2
assert lib.tslib_sum(xs, 0, ctypes.byref(out)) == TSLIB_ERR_INVALID
assert lib.tslib_sum(xs, -1, ctypes.byref(out)) == TSLIB_ERR_INVALID

print("sum=10 norm2≈5.477 max=4 err(NULL)=1 err(n<=0)=2")
print("sol-01 ctypes OK")
