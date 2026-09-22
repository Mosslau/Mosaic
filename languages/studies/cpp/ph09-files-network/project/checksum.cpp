// checksum.cpp —— FNV-1a 校验和实现
#include "checksum.h"

#include <cstdint>
#include <fstream>

namespace filesync {

std::uint32_t fnv1a(const char* buf, std::size_t n, std::uint32_t state) {
    for (std::size_t i = 0; i < n; ++i) {
        state ^= static_cast<std::uint8_t>(buf[i]);
        state *= 16777619u;
    }
    return state;
}

bool file_checksum(const std::string& path, std::uint32_t* sum_out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char buf[8192];
    std::uint32_t sum = fnv1a(nullptr, 0);
    for (;;) {
        in.read(buf, sizeof(buf));
        const std::streamsize n = in.gcount();
        if (n > 0) sum = fnv1a(buf, static_cast<std::size_t>(n), sum);
        if (in.eof()) break;
        if (in.fail()) return false;
    }
    *sum_out = sum;
    return true;
}

}  // namespace filesync
