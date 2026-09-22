// ex01-vector-oob.cpp —— 越界访问：三种“数组形态”与两种检测工具的覆盖差异
// 主题：vector::operator[] 不做边界检查（越界即 UB），at() 是检查版（越界抛
//       std::out_of_range，定义行为）；ASan 靠红区抓 vector/std::array 越界，
//       UBSan 只抓内建数组（int c[3]）的下标越界 —— 两种工具覆盖不同形态；
//       实测（本机 Apple clang 21.0.0）：越界写在 -O0/-O1/-O2 三档 + ASan 下均报
//       heap-buffer-overflow（越界写后紧跟对同一越界位置的 printf 读，写无法被优化器
//       消除）——UB 演示统一用 -O0 只为行号稳定、报告可控，不是防漏报（C 系 ph10 4.2
//       的“优化改变 UB 表现”演示针对可整体折叠的表达式，与本示例场景不同）。
// 运行前提（故意出错变体，勿裸跑）：
//   -DEX01_VEC_OOB    必须用 c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address 编译运行
//   -DEX01_STD_ARRAY  同上（std::array 越界读）
//   -DEX01_CARRAY     必须用 c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined
//                     -fno-sanitize-recover=all 编译运行（C 数组越界写）
// 默认（无 -D）编译零警告：打印“为什么 operator[] 不检查边界”的安全对照，可任意运行。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex01-vector-oob.cpp -o /tmp/ph15-ex01        （零警告）
// 运行：    /tmp/ph15-ex01
// 验证状态：已验证（默认零警告；三个故意出错变体报告实测记录于本文件底部注释）
#include <array>
#include <cstddef>
#include <cstdio>
#include <stdexcept>
#include <vector>

// 越界写：通过运行期下标越界 1 个元素（size=3、cap=3，越界写落在堆红区）
void demo_vec_oob() {
    std::vector<int> v = {1, 2, 3};      // size=3, cap=3（实测 libc++ 精确分配）
    std::size_t idx = 3;                 // 运行期下标：编译器无法静态拦截（无 -Warray-bounds）
    std::printf("vec: size=%zu cap=%zu, 写 v[%zu]=100 ...\n", v.size(), v.capacity(), idx);
    v[idx] = 100;                        // UB: 越界写（ASan 报 heap-buffer-overflow）
    std::printf("vec: v[%zu]=%d\n", idx, v[idx]);
}

// std::array 越界读：对象在栈上，ASan 报 stack-buffer-overflow；UBSan 对 operator[] 静默
void demo_std_array_oob() {
    std::array<int, 3> a = {1, 2, 3};
    std::size_t idx = 3;                 // 运行期下标
    std::printf("array: 读 a[%zu] ...\n", idx);
    std::printf("array: a[%zu]=%d\n", idx, a[idx]);   // UB: 越界读
}

// C 数组越界写：UBSan 直接插桩下标表达式，报 index out of bounds
void demo_carray_oob() {
    int c[3] = {1, 2, 3};
    std::size_t idx = 3;                 // 运行期下标
    std::printf("carr: 写 c[%zu]=7 ...\n", idx);
    c[idx] = 7;                          // UB: 越界写（UBSan 报 index 3 out of bounds for type 'int[3]'）
    std::printf("carr: c[%zu]=%d\n", idx, c[idx]);
}

int main() {
#if defined(EX01_VEC_OOB)
    demo_vec_oob();
#elif defined(EX01_STD_ARRAY)
    demo_std_array_oob();
#elif defined(EX01_CARRAY)
    demo_carray_oob();
#else
    // —— 安全对照（默认）：operator[] 无检查是 C++ 容器与 C 数组共享的 UB 缺口 ——
    std::printf("[1] vector::operator[] 不做边界检查：越界访问是 UB（编译器不拦、不报）\n");
    std::printf("    运行时护栏由工具补：ASan 红区抓越界（变体 -DEX01_VEC_OOB）；\n");
    std::printf("    at() 是标准库自带的检查版：越界抛 std::out_of_range（定义行为）\n");
    {
        std::vector<int> v = {1, 2, 3};
        try {
            std::printf("    v.at(3) -> %d\n", v.at(3));   // 抛异常
        } catch (const std::out_of_range&) {
            std::printf("    v.at(3) 抛出 std::out_of_range（at() 检查边界）\n");
        }
    }
    std::printf("[2] 手动边界检查：先判后取，是 at() 之外的通用写法\n");
    {
        std::vector<int> v = {1, 2, 3};
        const std::size_t idx = 3;
        if (idx < v.size()) {
            std::printf("    v[%zu] = %d\n", idx, v[idx]);
        } else {
            std::printf("    idx=%zu 越界（v.size()=%zu），拒绝访问 —— 返回错误\n", idx, v.size());
        }
    }
    std::printf("[3] 检测工具覆盖差异（本阶段实测）：ASan 抓 vector/std::array 越界\n");
    std::printf("    （heap/stack-buffer-overflow），UBSan 只抓内建数组下标越界；\n");
    std::printf("    两种工具都要用 —— 详见 -DEX01_STD_ARRAY / -DEX01_CARRAY 变体报告\n");
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0，-O0/-O1/-O2 -g 均触发）：
//   [默认] 输出 [1][2][3] 三组对照；-Wall -Wextra 零警告（Homebrew clang 21.1.8 同）
//   [-DEX01_VEC_OOB + ASan] 三档均退出码 134：
//     ERROR: AddressSanitizer: heap-buffer-overflow on address ...
//     WRITE of size 4 at ... thread T0
//     0x... is located 0 bytes after 12-byte region [0x...,0x...)
//     （三档报告一致：越界写后紧跟同下标 printf 读，写未被优化器消除 —— 折叠消失
//       需要“整段访问无观察者”；-O0 仅用于行号稳定/报告可控，不是防漏报）
//   [-DEX01_STD_ARRAY + ASan] 退出码 134：
//     ERROR: AddressSanitizer: stack-buffer-overflow ... READ of size 4
//     （同段代码 -fsanitize=undefined 实测无报告：UBSan 不检查 std::array::operator[]）
//   [-DEX01_CARRAY + UBSan] 退出码 134：
//     runtime error: index 3 out of bounds for type 'int[3]'
