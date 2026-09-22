// vec_index_wrap.cpp —— C 包装层：把 vindex::flat_index 以 C ABI 暴露
// 验证环境：Apple clang 21.0.0（C++20），实测编译零警告
// 验证状态：已验证（C 驱动 + Python ctypes 断言全绿）
// 教学点：核心类只抛异常、包装层全 catch 转错误码（异常不穿 C ABI）；
//         search 的结果写进「调用者提供的缓冲」= 零所有权转移（主文档 3.8 规则 2）；
//         返回指针的只有 create，且只允许库内 destroy 归还（opaque 纪律）。
#include "vec_index_api.h"
#include "vec_index_core.h"

#include <cstddef>
#include <new>
#include <stdexcept>
#include <vector>

namespace {

vindex::flat_index* as_cpp(vec_index* h) {
    return reinterpret_cast<vindex::flat_index*>(h);
}
const vindex::flat_index* as_cpp(const vec_index* h) {
    return reinterpret_cast<const vindex::flat_index*>(h);
}

}  // namespace

extern "C" vec_index* vec_index_create(int64_t dim) {
    try {
        auto* obj = new vindex::flat_index{dim};  // dim<=0 抛 invalid_argument
        return reinterpret_cast<vec_index*>(obj);
    } catch (...) {
        return nullptr;  // 分配失败与非法 dim 都压成空句柄（调用方判 NULL）
    }
}

extern "C" void vec_index_destroy(vec_index* idx) {
    delete as_cpp(idx);  // 只在本库 delete：跨侧释放是红线
}

extern "C" int vec_index_add(vec_index* idx, int64_t id, const float* v, int64_t dim) {
    if (idx == nullptr || v == nullptr) return VI_ERR_NULL;
    try {
        as_cpp(idx)->add(id, v, dim);
        return VI_OK;
    } catch (const std::invalid_argument&) {
        return VI_ERR_DIM;
    } catch (...) {
        return VI_ERR_BAD;
    }
}

extern "C" int vec_index_search(const vec_index* idx, const float* query, int64_t dim,
                                int64_t topk, vec_hit* out, int64_t cap, int64_t* count) {
    if (idx == nullptr || query == nullptr || out == nullptr || count == nullptr) {
        return VI_ERR_NULL;
    }
    if (cap < topk) return VI_ERR_CAP;  // 参数校验不进 try（无异常可抛）
    if (topk <= 0) return VI_OK;        // 语义：查 0 条，合法空操作
    try {
        const auto hits = as_cpp(idx)->search(query, dim, static_cast<std::size_t>(topk));
        for (std::size_t i = 0; i < hits.size(); ++i) {
            out[i].id = hits[i].id;      // 写调用者缓冲：布局 = vec_hit 数组
            out[i].dist = hits[i].dist;
        }
        *count = static_cast<int64_t>(hits.size());
        return VI_OK;
    } catch (const std::invalid_argument&) {
        return VI_ERR_DIM;
    } catch (const std::runtime_error&) {
        return VI_ERR_EMPTY;
    } catch (...) {
        return VI_ERR_BAD;
    }
}

extern "C" int vec_index_size(const vec_index* idx, int64_t* out) {
    if (idx == nullptr || out == nullptr) return VI_ERR_NULL;
    *out = static_cast<int64_t>(as_cpp(idx)->size());
    return VI_OK;
}

extern "C" int vec_index_version(void) {
    return 1;
}
