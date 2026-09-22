// ex01-stats-c-api.h —— C 包装层对外头文件：C 与 C++ 双编译器可 include
// 验证环境：clang（C11）/ clang++（C++20）同机双编译，实测通过
// 验证状态：已验证。这个头就是「最小公分母」契约本身——C 宿主、Python ctypes、
//           Rust extern "C" 都按它消费；改它等于同时改三种语言的约定。
#ifndef EX01_STATS_C_API_H
#define EX01_STATS_C_API_H

#ifdef __cplusplus
extern "C" {
#endif

/* 错误码：跨 C ABI 的错误一律走它，异常不出库（主文档 3.6） */
enum {
    VTEST_OK = 0,
    VTEST_ERR_NULL = 1,     /* 收到空句柄 / 空输出指针 */
    VTEST_ERR_EMPTY = 2,    /* 尚无样本，mean 无定义 */
    VTEST_ERR_VALUE = 3,    /* 非法数值（NaN） */
    VTEST_ERR_INTERNAL = 99 /* 其余异常兜底 */
};

/* opaque 句柄：完整类型（vtest::running_stats）藏在 C++ 侧，本头只有前向声明。
   任何一侧想直接 delete 它都会被编译器拒绝——销毁只能走 vtest_stats_destroy。 */
struct vtest_stats;
typedef struct vtest_stats vtest_stats;

/* 谁创建谁销毁：create/destroy 成对，new/delete 永远留在库内同一侧 */
vtest_stats* vtest_stats_create(void);
void vtest_stats_destroy(vtest_stats* s);

/* 成员函数 → C 函数：首参变句柄；返回错误码（0=成功，其余见上） */
int vtest_stats_add(vtest_stats* s, double value);
int vtest_stats_count(const vtest_stats* s, long* out);   /* out 指针由调用者分配 */
int vtest_stats_mean(const vtest_stats* s, double* out);

/* 版本检查：宿主/绑定先取版本再使用（ph19 3.7 纪律延伸到语言边界） */
int vtest_stats_version(void);

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif  /* EX01_STATS_C_API_H */
