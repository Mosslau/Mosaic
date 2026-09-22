# ex02-stats-ctypes.py —— Python ctypes 调 C++ 导出的 C ABI
# 验证环境：/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3（Python 3.13.12）
# 依赖：无（ctypes 是标准库）；前置：先按 ex01 编出 /tmp/libvtest.dylib
# 运行：python3 ex02-stats-ctypes.py（预期打印 count=3 mean=4.0 ... ctypes driver OK，退出码 0）
# 验证状态：已验证（本机实测通过）
# 教学点：argtypes/restype 是 ctypes 的类型安全护栏——不声明时指针默认当 int，
#         arm64 上 8 字节指针被截断成 4 字节 int，立刻段错误。声明即契约。
import ctypes

lib = ctypes.CDLL("/tmp/libvtest.dylib")

# 声明签名：句柄一律 c_void_p；out 参数用 POINTER(...)；错误码是 c_int
lib.vtest_stats_create.restype = ctypes.c_void_p
lib.vtest_stats_destroy.argtypes = [ctypes.c_void_p]
lib.vtest_stats_version.restype = ctypes.c_int
lib.vtest_stats_add.argtypes = [ctypes.c_void_p, ctypes.c_double]
lib.vtest_stats_add.restype = ctypes.c_int
lib.vtest_stats_mean.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
lib.vtest_stats_mean.restype = ctypes.c_int
lib.vtest_stats_count.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_long)]
lib.vtest_stats_count.restype = ctypes.c_int

assert lib.vtest_stats_version() >= 1, "version check failed"


# 语言侧 RAII 收口（主文档 3.8）：句柄包成类，__del__ 兜底归还库内销毁
class Stats:
    def __init__(self) -> None:
        self._h = lib.vtest_stats_create()
        if not self._h:
            raise MemoryError("create failed")

    def add(self, value: float) -> int:
        return lib.vtest_stats_add(self._h, value)

    def mean(self) -> float:
        out = ctypes.c_double()
        rc = lib.vtest_stats_mean(self._h, ctypes.byref(out))  # byref 传 out 指针
        if rc != 0:
            raise OSError(f"mean failed with code {rc}")
        return out.value

    def __del__(self) -> None:  # CPython 引用计数归零即触发，确定性高
        if getattr(self, "_h", None):
            lib.vtest_stats_destroy(self._h)
            self._h = None


s = Stats()
assert s.add(2.0) == 0
assert s.add(4.0) == 0
assert s.add(6.0) == 0
assert s.mean() == 4.0

# 错误路径：空样本 mean → 错误码 2（不是崩溃、不是异常穿库）
empty = Stats()
err_mean = ctypes.c_double()
err = lib.vtest_stats_mean(empty._h, ctypes.byref(err_mean))
assert err == 2, f"expected empty-index error 2, got {err}"

print("mean via ctypes = 4.0, empty-index err =", err)
print("ctypes driver OK")
