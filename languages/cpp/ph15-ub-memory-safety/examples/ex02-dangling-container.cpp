// ex02-dangling-container.cpp —— 悬空引用与迭代器/引用失效：容器生命周期是 C++ 特有的悬空源
// 主题：引用“也可能悬空”（roadmap 必会概念）——C++ 的引用不携带所有权，容器管理元素
//       生命周期，于是有两类容器相关悬空：① vector 扩容重分配后旧引用/迭代器失效
//       （std 标准保证：重分配使全部引用、指针、迭代器失效）；② 容器先于引用被销毁，
//       引用指向已释放的堆内存。返回局部对象引用的第三类悬空（F.43 + 编译器
//       -Wreturn-stack-address 告警）ph12 已系统讲透（其 ex05-dangling），本文件不重复。
// 运行前提（故意出错变体，勿裸跑）：
//   -DEX02_REALLOC      必须用 c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address 编译运行
//                       （扩容后使用旧引用 —— 报告 heap-use-after-free）
//   -DEX02_CONTAINER_DEAD 同上（容器销毁后使用引用 —— 报告 heap-use-after-free）
// 默认（无 -D）编译零警告：打印“安全容器使用”三模式，可任意运行。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex02-dangling-container.cpp -o /tmp/ph15-ex02
// 运行：    /tmp/ph15-ex02
// 验证状态：已验证（默认零警告；两个变体报告实测记录于本文件底部注释）
#include <cstddef>
#include <cstdio>
#include <string>
#include <vector>

// 危险路径 A：扩容重分配后使用旧引用（roadmap §15 示例的完整版）
void demo_realloc() {
    std::vector<int> v = {1, 2, 3};        // size=3, cap=3
    const int& r = v[0];                   // 引用元素
    const int* p = v.data();               // 指针元素
    std::printf("realloc: size=%zu cap=%zu, 持有 r/p 指向 v[0]\n", v.size(), v.capacity());
    v.push_back(4);                        // 触发重分配：cap 3 → 6（实测），旧缓冲区被释放
    std::printf("realloc: push_back 后 size=%zu cap=%zu（旧缓冲区已释放）\n", v.size(), v.capacity());
    std::printf("realloc: 读旧引用 r=%d ...\n", r);   // UB: 引用指向已释放的旧缓冲区
    std::printf("realloc: *p=%d\n", *p);              // （到不了这行：ASan 在上一行中止）
}

// 危险路径 B：容器先销毁，引用指向已释放的堆内存
void demo_container_dead() {
    auto* v = new std::vector<std::string>{"payload-0123456789"};
    const std::string& s = (*v)[0];        // 引用指向容器堆缓冲区内的 string 对象
    std::printf("dead: 持有引用 s 指向容器内元素\n");
    delete v;                              // 容器销毁：string 对象析构、堆缓冲区释放
    std::printf("dead: delete 容器后读 s.size() ...\n");
    std::printf("dead: s.size()=%zu\n", s.size());    // UB: use-after-free（读已释放堆内存）
}

int main() {
#if defined(EX02_REALLOC)
    demo_realloc();
#elif defined(EX02_CONTAINER_DEAD)
    demo_container_dead();
#else
    // —— 安全对照（默认）：容器元素的引用/迭代器必须随容器状态变化而“刷新” ——
    std::printf("[1] 扩容后会重分配：旧引用/迭代器失效 —— 用下标每次现取，不缓存\n");
    {
        std::vector<int> v = {1, 2, 3};
        v.push_back(4);                    // 扩容
        std::printf("    v[0]=%d（每次现取下标，绝无悬空）\n", v[0]);
    }
    std::printf("[2] 预留容量：reserve 消除“写满才扩容”的隐性失效\n");
    {
        std::vector<int> v;
        v.reserve(4);                      // 一次性预留
        const int* p = v.data();           // reserve 后、写满前 data() 稳定
        for (int i = 0; i < 4; ++i) v.push_back(i);
        std::printf("    *p=%d（reserve(4) 内 push_back 不扩容，指针仍有效）\n", *p);
    }
    std::printf("[3] 容器生命周期先于引用结束：先取值再放容器走（值语义 / 移动语义）\n");
    {
        std::vector<std::string> names = {"motor", "pump"};
        std::string first = names[0];      // 拷贝出值，names 随后的任何变化不影响 first
        names.clear();                     // 容器内容清空/销毁都与 first 无关
        std::printf("    first=%s（拷贝出的值不受容器影响）\n", first.c_str());
    }
    std::printf("[4] 返回局部引用的悬空（F.43）ph12 已讲透：本阶段聚焦容器生命周期这一源\n");
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0，-O0/-O1/-O2 -g 均触发）：
//   [默认] 输出 [1]~[4] 四组对照；-Wall -Wextra 零警告（Homebrew clang 21.1.8 同）
//   [-DEX02_REALLOC + ASan] 退出码 134（实测 -O0/-O1/-O2 均报）：
//     ERROR: AddressSanitizer: heap-use-after-free on address ... at pc ...
//     READ of size 4 at ... thread T0
//   [-DEX02_CONTAINER_DEAD + ASan] 退出码 134：
//     ERROR: AddressSanitizer: heap-use-after-free ... READ of size 1
//   （本环境 ASan 无法启动外部符号器（llvm-symbolizer spawn 失败 errno 9），
//     报告栈帧未符号化，但错误类型/访问大小/分配释放信息完整）
