# search_python.py —— Python 侧：ctypes 调 C++ 向量检索库（阶段项目验收用）
# 验证环境：Python 3.13.12（/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3）
# 前置：make（编译出 /tmp/libvecindex.dylib）
# 运行：python3 search_python.py（预期断言全绿、退出码 0）
# 验证状态：已验证
# 教学点：跨语言 struct（vec_hit）用 ctypes.Structure 描述同一份字节（主文档 4.1）；
#         float 数组 = 指针 + 长度；结果缓冲由调用者分配（零所有权转移）；
#         索引句柄生命周期用 Python 类收口（__del__ 调 destroy，主文档 3.8）。
import ctypes

lib = ctypes.CDLL("/tmp/libvecindex.dylib")

VI_OK, VI_ERR_NULL, VI_ERR_DIM, VI_ERR_EMPTY, VI_ERR_CAP = 0, 1, 2, 3, 5


class VecHit(ctypes.Structure):  # 与 vec_index_api.h 的 vec_hit 逐字段一致
    _fields_ = [("id", ctypes.c_int64), ("dist", ctypes.c_float)]


lib.vec_index_version.restype = ctypes.c_int
lib.vec_index_create.argtypes = [ctypes.c_int64]
lib.vec_index_create.restype = ctypes.c_void_p
lib.vec_index_destroy.argtypes = [ctypes.c_void_p]
lib.vec_index_add.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_float), ctypes.c_int64]
lib.vec_index_add.restype = ctypes.c_int
lib.vec_index_size.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
lib.vec_index_size.restype = ctypes.c_int
lib.vec_index_search.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.c_int64,
    ctypes.c_int64,
    ctypes.POINTER(VecHit),
    ctypes.c_int64,
    ctypes.POINTER(ctypes.c_int64),
]
lib.vec_index_search.restype = ctypes.c_int

assert lib.vec_index_version() >= 1


class VecIndex:  # 语言侧 RAII 收口：句柄只在析构时归还库内
    def __init__(self, dim: int) -> None:
        self._h = lib.vec_index_create(dim)
        if not self._h:
            raise MemoryError("create failed (dim<=0 or OOM)")

    def add(self, vid: int, vec: list[float]) -> None:
        arr = (ctypes.c_float * len(vec))(*vec)
        rc = lib.vec_index_add(self._h, vid, arr, len(vec))
        if rc != VI_OK:
            raise OSError(f"add failed, code={rc}")

    def search(self, query: list[float], topk: int) -> list[VecHit]:
        q = (ctypes.c_float * len(query))(*query)
        hits = (VecHit * topk)()  # 调用者分配结果缓冲（cap=topk）
        count = ctypes.c_int64()
        rc = lib.vec_index_search(self._h, q, len(query), topk, hits, topk, ctypes.byref(count))
        if rc != VI_OK:
            raise OSError(f"search failed, code={rc}")
        return list(hits[: count.value])

    def __del__(self) -> None:
        if getattr(self, "_h", None):
            lib.vec_index_destroy(self._h)
            self._h = None


idx = VecIndex(3)
idx.add(100, [1.0, 0.0, 0.0])
idx.add(200, [0.0, 1.0, 0.0])
idx.add(300, [0.0, 0.0, 1.0])
idx.add(400, [1.0, 1.0, 0.0])

# 维度错误路径在 Python 侧表现为异常而非崩溃
try:
    idx.add(500, [1.0, 0.0])  # dim=2 != 索引 dim=3
except OSError as exc:
    assert "code=2" in str(exc)  # VI_ERR_DIM
else:
    raise AssertionError("expected OSError for dim mismatch")

# 空索引 search → VI_ERR_EMPTY
empty = VecIndex(3)
try:
    empty.search([0.9, 0.1, 0.0], 1)
except OSError as exc:
    assert "code=3" in str(exc)
else:
    raise AssertionError("expected OSError on empty index")

# 正常 top3：期望 id 序 [100, 400, 200]（与 C 驱动同一份数据互证）
hits = idx.search([0.9, 0.1, 0.0], 3)
assert [(h.id, round(h.dist, 4)) for h in hits] == [(100, 0.02), (400, 0.82), (200, 1.62)], hits

print("python search OK: top3 = [(100, 0.02), (400, 0.82), (200, 1.62)]")
print("search_python.py PASS")
