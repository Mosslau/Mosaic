// sol-04-endian-serialize.cpp —— 练习 4 参考实现：字节序无关的二进制序列化
// 练习 4 要求：实现 uint16/uint32 的"大端（网络序）"序列化与反序列化，
// 不依赖平台字节序；round-trip 自测 + 运行期字节序探测。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   c++ -std=c++20 -Wall -Wextra sol-04-endian-serialize.cpp -o /tmp/sol-04 && /tmp/sol-04
//     runtime endianness: little
//     uint16 0x1234 -> bytes 12 34 -> back 0x1234 (OK)
//     uint32 0x01020304 -> bytes 01 02 03 04 -> back 0x01020304 (OK)
//     uint32 0xDEADBEEF -> bytes DE AD BE EF -> back 0xDEADBEEF (OK)
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 验证状态：已验证（两种编译器均零警告，round-trip 全部 OK）
#include <cstdint>
#include <cstdio>

// 大端序列化：把主机序整数拆成 4 字节，先写高位（网络序约定）
void put_u16be(uint16_t v, unsigned char out[2]) {
    out[0] = static_cast<unsigned char>((v >> 8) & 0xFFu);
    out[1] = static_cast<unsigned char>(v & 0xFFu);
}

void put_u32be(uint32_t v, unsigned char out[4]) {
    out[0] = static_cast<unsigned char>((v >> 24) & 0xFFu);
    out[1] = static_cast<unsigned char>((v >> 16) & 0xFFu);
    out[2] = static_cast<unsigned char>((v >> 8) & 0xFFu);
    out[3] = static_cast<unsigned char>(v & 0xFFu);
}

// 大端反序列化：与 put_* 互逆，不关心主机字节序
uint16_t get_u16be(const unsigned char in[2]) {
    return static_cast<uint16_t>((static_cast<uint16_t>(in[0]) << 8) | in[1]);
}

uint32_t get_u32be(const unsigned char in[4]) {
    return (static_cast<uint32_t>(in[0]) << 24) | (static_cast<uint32_t>(in[1]) << 16) |
           (static_cast<uint32_t>(in[2]) << 8) | in[3];
}

int main() {
    // 运行期字节序探测（可移植，不依赖编译器宏）
    const uint16_t probe = 0x0102u;
    const auto* pb = reinterpret_cast<const unsigned char*>(&probe);
    std::printf("runtime endianness: %s\n", pb[0] == 0x02u ? "little" : "big");

    // uint16 round-trip
    const uint16_t v16 = 0x1234u;
    unsigned char b16[2];
    put_u16be(v16, b16);
    std::printf("uint16 0x%04X -> bytes %02X %02X -> back 0x%04X %s\n",
                v16, b16[0], b16[1], get_u16be(b16),
                get_u16be(b16) == v16 ? "(OK)" : "(FAIL)");

    // uint32 round-trip × 2
    const uint32_t vals[2] = {0x01020304u, 0xDEADBEEFu};
    for (uint32_t v : vals) {
        unsigned char b32[4];
        put_u32be(v, b32);
        std::printf("uint32 0x%08X -> bytes %02X %02X %02X %02X -> back 0x%08X %s\n",
                    v, b32[0], b32[1], b32[2], b32[3], get_u32be(b32),
                    get_u32be(b32) == v ? "(OK)" : "(FAIL)");
    }
    return 0;
}
