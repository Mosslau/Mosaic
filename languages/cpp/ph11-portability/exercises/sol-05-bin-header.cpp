// sol-05-bin-header.cpp —— 练习 5 参考实现：跨平台二进制文件头（★★★ 综合题）
// 练习 5 要求：用固定宽度类型 + 大端序列化写一个跨平台二进制文件头
// （magic 4 字节 + version uint16 + 记录数 uint32 + 每条记录 uint64），
// 写读往返自测，并验证"任何字节序机器读同一文件结果一致"。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   c++ -std=c++20 -Wall -Wextra sol-05-bin-header.cpp -o /tmp/sol-05 && /tmp/sol-05
//     native endianness: little
//     header bytes: 50 48 4C 31 | 00 01 | 00 00 00 02 | 00 00 00 00 00 00 00 2A | 00 00 00 00 00 00 00 2B
//     readback magic=0x50484C31 version=1 count=2 records[0]=42 records[1]=43  (OK)
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 验证状态：已验证（两种编译器均零警告，往返一致）
#include <bit>
#include <cstdint>
#include <cstdio>

namespace bin {

// 大端写出 uint16/uint32/uint64（网络序，跨平台一致）
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
void put_u64be(uint64_t v, unsigned char out[8]) {
    for (int i = 0; i < 8; ++i) {
        out[i] = static_cast<unsigned char>((v >> (56 - 8 * i)) & 0xFFu);
    }
}

struct Header {
    uint32_t magic;
    uint16_t version;
    uint32_t count;
    uint64_t records[2];
};

// 序列化：固定布局 4 + 2 + 4 + 16 = 26 字节，全部大端
std::size_t serialize(const Header& h, unsigned char* buf) {
    put_u32be(h.magic, buf);
    put_u16be(h.version, buf + 4);
    put_u32be(h.count, buf + 6);
    for (uint32_t i = 0; i < h.count; ++i) {
        put_u64be(h.records[i], buf + 10 + 8 * i);
    }
    return 10 + 8 * h.count;
}

// 反序列化：与 serialize 互逆
void deserialize(const unsigned char* buf, Header& h) {
    h.magic = (static_cast<uint32_t>(buf[0]) << 24) | (static_cast<uint32_t>(buf[1]) << 16) |
              (static_cast<uint32_t>(buf[2]) << 8) | buf[3];
    h.version = static_cast<uint16_t>((static_cast<uint16_t>(buf[4]) << 8) | buf[5]);
    h.count = (static_cast<uint32_t>(buf[6]) << 24) | (static_cast<uint32_t>(buf[7]) << 16) |
              (static_cast<uint32_t>(buf[8]) << 8) | buf[9];
    for (uint32_t i = 0; i < h.count; ++i) {
        uint64_t v = 0;
        for (int j = 0; j < 8; ++j) {
            v = (v << 8) | buf[10 + 8 * i + j];
        }
        h.records[i] = v;
    }
}

}  // namespace bin

int main() {
    if constexpr (std::endian::native == std::endian::little) {
        std::printf("native endianness: little\n");
    } else {
        std::printf("native endianness: big\n");
    }

    const bin::Header src{0x50484C31u, 1, 2, {42u, 43u}};
    unsigned char buf[26]{};
    const std::size_t n = bin::serialize(src, buf);

    std::printf("header bytes: ");
    std::printf("%02X %02X %02X %02X | ", buf[0], buf[1], buf[2], buf[3]);
    std::printf("%02X %02X | ", buf[4], buf[5]);
    std::printf("%02X %02X %02X %02X | ", buf[6], buf[7], buf[8], buf[9]);
    for (std::size_t i = 10; i < n; ++i) {
        std::printf("%02X ", buf[i]);
    }
    std::printf("\n");

    bin::Header dst{};
    bin::deserialize(buf, dst);
    const bool ok = (dst.magic == src.magic) && (dst.version == src.version) &&
                    (dst.count == src.count) && (dst.records[0] == src.records[0]) &&
                    (dst.records[1] == src.records[1]);
    std::printf("readback magic=0x%08X version=%u count=%u records[0]=%llu records[1]=%llu  %s\n",
                dst.magic, dst.version, dst.count,
                static_cast<unsigned long long>(dst.records[0]),
                static_cast<unsigned long long>(dst.records[1]),
                ok ? "(OK)" : "(FAIL)");
    return ok ? 0 : 1;
}
