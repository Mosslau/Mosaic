// ex06-alias-align.cpp —— 类型别名与对齐：两类“看不见”的 UB 与正解
// 主题：① 严格别名（strict aliasing，[basic.lval]）：同一内存只能通过类型兼容的
//       glvalue 访问（char 系列例外）——reinterpret_cast 双关、union 读非活动成员都
//       是 UB；正解是 std::bit_cast（C++20）或 memcpy。② 对齐（[basic.align]）：
//       通过未对齐地址访问对象是 UB——现代 arm64 硬件容忍未对齐访问（实测不崩），
//       但仍是 UB，UBSan 一视同仁地报告。两类都是“工具难抓/靠规范”的典型。
// 运行前提（故意出错变体）：
//   -DEX06_PUN_PTR      别名违规（指针双关）：可任意编译运行，但输出是 UB 的
//                       “碰巧正确”表现（实测 -O0/-O2 一致）——不能证明安全
//   -DEX06_PUN_UNION    union 读非活动成员（C++ 中 UB）：同上，工具抓不到
//   -DEX06_MISALIGN    必须用 c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined
//                       -fno-sanitize-recover=all 编译运行（未对齐访问 → UBSan 报告）
// 默认（无 -D）编译零警告：打印正解对照（std::bit_cast / memcpy / 对齐安全写法），可任意运行。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex06-alias-align.cpp -o /tmp/ph15-ex06
// 运行：    /tmp/ph15-ex06
// 验证状态：已验证（默认零警告；变体实测记录于本文件底部注释）
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstring>

// 危险 A：reinterpret_cast 指针双关 —— 违反严格别名（与 C ph10 的 *(float*)&u32 同构）
void pun_via_pointer() {
    float f = 1.0f;                        // 位模式 0x3F800000
    auto* u = reinterpret_cast<std::uint32_t*>(&f);   // UB: 以 uint32_t 访问 float 对象
    std::printf("pun_ptr: bits=%08x\n", *u);          // “碰巧正确”的 UB 表现
}

// 危险 B：union 读非活动成员 —— C++ 中同样是 UB（[class.union] 只豁免 common initial sequence）
void pun_via_union() {
    union Bits {
        float f;
        std::uint32_t u;
    };
    Bits b;
    b.f = 1.0f;
    std::printf("pun_union: bits=%08x\n", b.u);       // UB: 读非活动成员 b.u
}

// 危险 C：未对齐访问 —— reinterpret_cast 造出未对齐地址
void misaligned_store() {
    alignas(std::uint32_t) unsigned char buf[8] = {0};
    auto* p = reinterpret_cast<std::uint32_t*>(buf + 1);  // buf+1 不是 4 字节对齐
    std::printf("align: 向未对齐地址 buf+1 写 uint32_t ...\n");
    *p = 0x11223344;                       // UB: 未对齐存储（UBSan 报告；arm64 裸跑不崩）
    std::printf("align: *p=%08x\n", *p);
}

int main() {
#if defined(EX06_PUN_PTR)
    pun_via_pointer();
#elif defined(EX06_PUN_UNION)
    pun_via_union();
#elif defined(EX06_MISALIGN)
    misaligned_store();
#else
    // —— 正解对照（默认）：位模式转换与对齐安全写法 ——
    std::printf("[1] 类型双关正解：std::bit_cast（C++20，定义行为）\n");
    {
        float f = 1.0f;
        std::uint32_t bits = std::bit_cast<std::uint32_t>(f);
        float back = std::bit_cast<float>(bits);
        std::printf("    bit_cast: bits=%08x back=%.1f\n", bits, static_cast<double>(back));
    }
    std::printf("[2] memcpy 双关（C++03 起的老写法）：编译器优化成单指令，等价安全\n");
    {
        float f = 1.0f;
        std::uint32_t bits = 0;
        static_assert(sizeof bits == sizeof f);
        std::memcpy(&bits, &f, sizeof bits);
        std::printf("    memcpy: bits=%08x\n", bits);
    }
    std::printf("[3] 读字节流的安全姿势：先 memcpy 到对齐变量，再读字段（永不强转）\n");
    {
        alignas(std::uint32_t) unsigned char buf[8] = {0x44, 0x33, 0x22, 0x11};
        std::uint32_t v = 0;
        std::memcpy(&v, buf, sizeof v);    // 对齐安全：memcpy 保证
        std::printf("    memcpy 读出: %08x\n", v);
    }
    std::printf("[4] 本文件故意出错变体：-DEX06_PUN_PTR / -DEX06_PUN_UNION（别名，工具抓不到）、\n");
    std::printf("    -DEX06_MISALIGN（未对齐，UBSan 报告）—— 详见文件底部注释\n");
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0；默认零警告，Homebrew clang 21.1.8 同）：
//   [默认] 输出 [1] bits=3f800000 back=1.0；[2] bits=3f800000；[3] 读出 11223344
//   [-DEX06_PUN_PTR] 实测 -O0/-O2 均输出 bits=3f800000 —— 与正解相同（“碰巧正确”：
//     本次 clang 未按别名假设重排；换代码形状/编译器/版本即可能不同 —— UB 判断依标准）
//   [-DEX06_PUN_UNION] 实测输出 bits=3f800000，UBSan 零报告（工具抓不到 union 双关）
//     （注意：GCC/Clang 把 union 双关当扩展接受（C 中为惯用法，见 C ph10），
//       但 C++ 标准只豁免 common initial sequence —— 跨编译器不保证）
//   [-DEX06_MISALIGN + UBSan] 退出码 134：
//     runtime error: store to misaligned address 0x... for type 'std::uint32_t'
//     (aka 'unsigned int'), which requires 4 byte alignment
//   （同代码 arm64 裸跑实测正常输出 read=11223344 —— 硬件容忍 ≠ 不是 UB）
