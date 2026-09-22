// bad_demos.cpp —— C++ UB 示例集：8 类 UB 的坏版本（故意出错，勿裸跑）
// 本文件全部函数都是“故意写错的 UB 演示”，设计上依赖 Sanitizer 中止：
//   - 构建默认 -fsanitize=address,undefined -fno-sanitize-recover=all -O0（见 Makefile），
//     坏版本一触发即报错退出（ASan/UBSan 报告见 project/README.md 实测表）；
//   - 禁止去掉 Sanitizer 后运行（裸跑可能崩溃或静默损坏数据）；
//   - 编译用 -Wno-uninitialized 抑制 bad_uninit 故意触发的 -Wuninitialized 警告
//     （教学点：该警告本身就是“编译器在编译期就能拦一部分坑”的证据）；
//   - 本文件不是零警告样板，坏版本故意触发警告/UB 的部分已在行内注释标明。
// 验证环境：Apple clang 21.0.0（c++）+ Homebrew clang 21.1.8（clang++），C++20
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <utility>
#include <vector>

// 1. 越界访问：vector 下标越界写（运行期下标：编译器无法静态拦截）
void bad_oob() {
    std::vector<int> v = {1, 2, 3};        // size=3, cap=3
    const std::size_t idx = 3;
    std::printf("[bad-oob] v.size=%zu cap=%zu，写 v[%zu]=100 ...\n", v.size(), v.capacity(), idx);
    v[idx] = 100;                          // UB: 越界写（ASan 报 heap-buffer-overflow）
    std::printf("[bad-oob] v[%zu]=%d\n", idx, v[idx]);   // 到不了这行
}

// 2. 悬空引用（容器生命周期）：引用指向已销毁容器的元素（new/delete 故意制造）
void bad_dangling() {
    auto* v = new std::vector<std::string>{"payload-0123456789"};
    const std::string& s = (*v)[0];        // 引用指向容器堆缓冲区内的元素
    std::printf("[bad-dangling] 持有引用 s；delete 容器 ...\n");
    delete v;                              // 容器销毁：元素析构、缓冲区释放
    std::printf("[bad-dangling] 读 s.size() ...\n");
    std::printf("[bad-dangling] s.size()=%zu\n", s.size());  // UB: use-after-free
}

// 3. use-after-free：delete 后继续写
void bad_uaf() {
    int* p = new int(42);
    std::printf("[bad-uaf] *p=%d；delete 后写 *p=1 ...\n", *p);
    delete p;                              // p 成为悬空指针
    *p = 1;                                // UB: use-after-free（ASan 报 WRITE）
    std::printf("[bad-uaf] *p=%d\n", *p);  // 到不了这行
}

// 4. 重复释放：同一指针 delete 两次
void bad_double_free() {
    int* p = new int(42);
    std::printf("[bad-double-free] *p=%d；连续两次 delete ...\n", *p);
    delete p;
    delete p;                              // UB: double free（ASan 报 attempting double-free）
    std::printf("[bad-double-free] 返回（到不了这行）\n");
}

// 5. use-after-move：解引用 moved-from 的 unique_ptr
void bad_uam() {
    auto up = std::make_unique<int>(42);
    auto moved = std::move(up);            // 所有权转移：up 保证为空
    std::printf("[bad-uam] moved-from up 为空；解引用 *up ...\n");
    std::printf("[bad-uam] *up=%d\n", *up);  // UB: 解引用空指针（UBSan 报 reference binding to null）
    (void)moved;
}

// 6. 类型双关（严格别名违规）：reinterpret_cast 以 uint32_t 访问 float 对象
void bad_alias() {
    float f = 1.0f;
    auto* u = reinterpret_cast<std::uint32_t*>(&f);   // UB: 违反严格别名（[basic.lval]）
    std::printf("[bad-alias] bits=%08x（碰巧正确的 UB 表现，无运行时报告）\n", *u);
}

// 7. 未对齐访问：reinterpret_cast 造出未对齐地址
void bad_align() {
    alignas(std::uint32_t) unsigned char buf[8] = {0};
    auto* p = reinterpret_cast<std::uint32_t*>(buf + 1);   // buf+1 非 4 字节对齐
    std::printf("[bad-align] 向未对齐地址 buf+1 写 uint32_t ...\n");
    *p = 0x11223344;                       // UB: 未对齐存储（UBSan 报 misaligned address）
    std::printf("[bad-align] *p=%08x\n", *p);  // 到不了这行
}

// 8. 未初始化变量：局部变量 + 平凡结构体成员（无运行时报告，编译期警告 + 垃圾值）
void bad_uninit() {
    int x;                                 // 未初始化（-Wuninitialized 会警告，此处被 BADFLAGS 抑制）
    struct Stats {
        int hits;
        int misses;
    };
    Stats s;                               // 成员未初始化（多数编译器不警告成员）
    std::printf("[bad-uninit] x=%d s.hits=%d（读不确定值：无 Sanitizer 报告，输出垃圾）\n",
                x, s.hits);
}
