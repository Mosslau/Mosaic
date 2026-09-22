// vec_index_api.h —— C ABI 头：C 与 C++ 双编译器可 include（互操作的唯一权威契约）
// 验证环境：clang（C11）/ clang++（C++20）
// 验证状态：已验证（C 驱动与 Python ctypes 都按本头调用并通过）
#ifndef VEC_INDEX_API_H
#define VEC_INDEX_API_H

#include <stdint.h>  /* int64_t：跨语言定宽，禁止裸 int（宽度随平台漂移） */

#ifdef __cplusplus
extern "C" {
#endif

/* 错误码：所有失败都落到这里，异常不出库 */
enum {
    VI_OK = 0,
    VI_ERR_NULL = 1,    /* 空句柄 / 空向量 / 空输出 */
    VI_ERR_DIM = 2,     /* 向量维度与索引维度不一致 */
    VI_ERR_EMPTY = 3,   /* 索引为空时 search */
    VI_ERR_CAP = 5,     /* 结果容量 cap < topk */
    VI_ERR_BAD = 99     /* 其余异常兜底 */
};

/* 检索结果：定宽 + repr(C) 布局，C/Python(ctypes)/Rust 三方按同一字节解释（主文档 4.1） */
typedef struct vec_hit {
    int64_t id;
    float dist;
} vec_hit;

/* opaque 句柄：完整类型藏在 C++ 侧 */
struct vec_index;
typedef struct vec_index vec_index;

vec_index* vec_index_create(int64_t dim);        /* dim<=0 时返回 NULL */
void vec_index_destroy(vec_index* idx);          /* 谁创建谁销毁：库内释放 */
int vec_index_add(vec_index* idx, int64_t id, const float* v, int64_t dim);
int vec_index_search(const vec_index* idx, const float* query, int64_t dim,
                     int64_t topk, vec_hit* out, int64_t cap, int64_t* count);
int vec_index_size(const vec_index* idx, int64_t* out);
int vec_index_version(void);                     /* 版本检查（ph19 3.7） */

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif  /* VEC_INDEX_API_H */
