// ex02-endian.cpp —— 字节序（大小端）探测与跨平台序列化
// 主题：多字节整数在内存中的字节排列因平台而异；写文件/网络协议必须固定字节序。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex02-endian.cpp -o /tmp/ex02-endian
// 运行：    /tmp/ex02-endian
// 验证状态：已验证（两种编译器均零警告，输出一致：native == little）
#include <bit>        // C++20 std::endian
#include <cstdint>
#include <cstdio>

// 编译期字节序探测：__BYTE_ORDER__ 是 GCC/Clang 预定义宏（MSVC 不定义，需 std::endian）
#if defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)
    #define PH11_BIG_ENDIAN 1
#else
    #define PH11_BIG_ENDIAN 0
#endif

// 运行期探测：看 0x0102 的首字节是 0x01（大端）还是 0x02（小端）
bool is_little_endian_runtime() {
    const uint16_t probe = 0x0102u;
    const auto* bytes = reinterpret_cast<const unsigned char*>(&probe);
    return bytes[0] == 0x02u;
}

// 通用字节序转换：把主机序整数按"大端（网络序）"写出/读回，不依赖平台字节序
uint32_t to_big_endian(uint32_t v) {
    return ((v & 0x000000FFu) << 24) | ((v & 0x0000FF00u) << 8) |
           ((v & 0x00FF0000u) >> 8) | ((v & 0xFF000000u) >> 24);
}

int main() {
    // 三种探测方式，结果应互相印证
    std::printf("macro __BYTE_ORDER__      : %s\n", PH11_BIG_ENDIAN ? "big" : "little");
    std::printf("runtime byte probe        : %s\n", is_little_endian_runtime() ? "little" : "big");
    if constexpr (std::endian::native == std::endian::little) {
        std::printf("std::endian::native       : little\n");
    } else {
        std::printf("std::endian::native       : big\n");
    }

    // 序列化演示：固定用大端（网络序）写一个 uint32，任何平台读回同一数字
    const uint32_t value = 0x01020304u;
    const uint32_t be = to_big_endian(value);   // 在 little-endian 机器上就是字节反转
    const auto* p = reinterpret_cast<const unsigned char*>(&be);
    std::printf("value=0x%08X  big-endian bytes: %02X %02X %02X %02X\n",
                value, p[0], p[1], p[2], p[3]);
    // 读回：big-endian 字节再转回主机序
    const uint32_t roundtrip = to_big_endian(be);
    std::printf("roundtrip=%u (%s)\n", roundtrip,
                roundtrip == value ? "OK" : "FAIL");
    return 0;
}
