// ex05-filexfer.cpp —— 文件传输工具：二进制分块读写 + 校验和
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex05-filexfer.cpp -o ex05
// 运行：
//   ./ex05 selftest               —— 自动验证：生成随机文件 → 分块复制 → 校验一致
//   ./ex05 <src> <dst>            —— 手动模式：复制文件并输出 FNV-1a 校验和
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <string>

// FNV-1a 滚动校验：state 跨块累积，保证"读到的字节就是写出的字节"
static uint32_t checksum(uint32_t state, const char* buf, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        state ^= static_cast<uint8_t>(buf[i]);
        state *= 16777619u;
    }
    return state;
}

// 分块复制 src → dst，返回累计校验和；读不满块用 gcount 处理
static bool copy_chunked(const std::string& src, const std::string& dst,
                         uint32_t* sum_out) {
    std::ifstream in(src, std::ios::binary);
    std::ofstream out(dst, std::ios::binary);
    if (!in || !out) return false;
    char buf[8192];
    uint32_t sum = 2166136261u;
    for (;;) {
        in.read(buf, sizeof(buf));               // 一次最多读一块
        const std::streamsize n = in.gcount();   // 实际读到的字节数（可能不满）
        if (n > 0) {
            out.write(buf, n);
            sum = checksum(sum, buf, static_cast<size_t>(n));
        }
        if (in.eof()) break;                     // 正常读完
        if (in.fail() || !out) return false;     // 读/写出错立即失败
    }
    *sum_out = sum;
    return true;
}

// 读文件并返回校验和（用于复制后验证一致性）
static bool checksum_file(const std::string& path, uint32_t* sum_out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char buf[8192];
    uint32_t sum = 2166136261u;
    for (;;) {
        in.read(buf, sizeof(buf));
        const std::streamsize n = in.gcount();
        if (n > 0) sum = checksum(sum, buf, static_cast<size_t>(n));
        if (in.eof()) break;
        if (in.fail()) return false;
    }
    *sum_out = sum;
    return true;
}

// 自测：生成随机二进制文件 → 复制 → 源/目标校验和一致
static int run_selftest() {
    const std::string src = "/tmp/ph09_xfer_src.bin";
    const std::string dst = "/tmp/ph09_xfer_dst.bin";
    {
        std::ofstream out(src, std::ios::binary);
        std::mt19937 rng(42);
        char buf[8192];
        for (int i = 0; i < 32; ++i) {
            for (char& c : buf) c = static_cast<char>(rng() & 0xff);
            out.write(buf, sizeof(buf));
        }
    }
    uint32_t src_sum = 0, dst_sum = 0;
    if (!copy_chunked(src, dst, &src_sum)) { std::cerr << "copy failed\n"; return 1; }
    if (!checksum_file(dst, &dst_sum)) { std::cerr << "verify failed\n"; return 1; }
    if (src_sum != dst_sum) { std::cerr << "checksum mismatch\n"; return 1; }
    std::cout << "copied 262144 bytes, checksum=0x" << std::hex << src_sum
              << std::dec << " (src == dst) OK\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "selftest") return run_selftest();
    if (argc != 3) {
        std::cerr << "usage: ./ex05 selftest | <src> <dst>\n";
        return 1;
    }
    uint32_t sum = 0;
    if (!copy_chunked(argv[1], argv[2], &sum)) {
        std::cerr << "transfer failed\n";
        return 1;
    }
    std::cout << "copied checksum=0x" << std::hex << sum << std::dec << '\n';
    return 0;
}
