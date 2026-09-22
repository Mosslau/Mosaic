/* vector_math.h —— ex04 的 C 侧头文件：一个「真实存在的 C 库」的接口。
 *
 * 它的消费方不是 C 程序，而是 Rust（通过 bindgen 在构建期扫描本头文件生成绑定）。
 * 教学点：bindgen 的输入就是这种普通头文件——C 库无需为 Rust 做任何改造，
 * Rust 侧「把 C 声明翻译成 Rust extern 块」的动作被工具自动化。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）；编译在 build.rs 内自动完成。
 */
#ifndef VECTOR_MATH_H
#define VECTOR_MATH_H

#include <stddef.h>

/* 点积：Σ a[i]*b[i]。n 为元素个数；a/b 为长度至少 n 的数组。 */
double vm_dot(const double *a, const double *b, size_t n);

/* 欧氏距离：sqrt(Σ (a[i]-b[i])²)。 */
double vm_euclidean(const double *a, const double *b, size_t n);

#endif /* VECTOR_MATH_H */
