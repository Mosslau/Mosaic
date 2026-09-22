# ex02-stats-cffi.py —— Python cffi（ABI 模式）调 C++ 导出的 C ABI
# 验证环境：Python 3.13.12 + cffi；cffi 未在本环境 pip 安装 → 标注「未在本环境验证」
# 安装：/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m pip install cffi
# 前置：先按 ex01 编出 /tmp/libvtest.dylib
# 运行：python3 ex02-stats-cffi.py
# 验证状态：未在本环境验证（cffi 未安装）；安装后按上述命令运行即得
# 教学点：cffi 的 ABI 模式把 C 声明写成字符串、在运行期解析绑定——声明即文档，
#         签名错误在加载期就暴露（ctypes 要到调用/错误路径才暴露）。声明用 C 语法
#         include 注释即可，不需要真实头文件存在（ffi.cdef 只解析文本）。
import cffi

ffi = cffi.FFI()

# 只需写出用到的最小声明（与 ex01-stats-c-api.h 逐字一致的子集）
ffi.cdef(
    """
    typedef struct vtest_stats vtest_stats;
    vtest_stats* vtest_stats_create(void);
    void vtest_stats_destroy(vtest_stats* s);
    int vtest_stats_add(vtest_stats* s, double value);
    int vtest_stats_mean(const vtest_stats* s, double* out);
    int vtest_stats_version(void);
    """
)

lib = ffi.dlopen("/tmp/libvtest.dylib")  # ABI 模式：运行期按声明 dlopen，无编译器参与

assert lib.vtest_stats_version() >= 1

s = lib.vtest_stats_create()
assert s != ffi.NULL
assert lib.vtest_stats_add(s, 2.0) == 0
assert lib.vtest_stats_add(s, 4.0) == 0
assert lib.vtest_stats_add(s, 6.0) == 0

mean = ffi.new("double *")
assert lib.vtest_stats_mean(s, mean) == 0
assert abs(mean[0] - 4.0) < 1e-9

# 错误路径：空样本 mean → 错误码 2
empty = lib.vtest_stats_create()
err = lib.vtest_stats_mean(empty, mean)
assert err == 2, f"expected error 2, got {err}"

lib.vtest_stats_destroy(s)
lib.vtest_stats_destroy(empty)
print("mean via cffi =", mean[0], "empty-index err =", err)
print("cffi driver OK")
