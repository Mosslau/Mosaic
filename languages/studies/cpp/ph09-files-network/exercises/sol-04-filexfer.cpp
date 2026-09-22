// sol-04-filexfer.cpp —— 练习 4 参考实现：文件传输工具（send/verify 子命令 + FNV-1a 校验）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra sol-04-filexfer.cpp -o sol-04
// 运行：
//   ./sol-04 selftest               —— 自动验证：随机文件 → send → verify 通过；篡改 → verify 失败
//   ./sol-04 send <src> <dst>       —— 手动模式：分块复制并输出校验和
//   ./sol-04 verify <file> <checksum-hex>
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <random>
#include <string>

// FNV-1a：初值 2166136261u，乘子 16777619u
static uint32_t fnv1a(const char* buf, size_t n, uint32_t state = 2166136261u) {
    for (size_t i = 0; i < n; ++i) {
        state ^= static_cast<uint8_t>(buf[i]);
        state *= 16777619u;
    }
    return state;
}

// 分块复制 src → dst，返回累计校验和；gcount 处理读不满块
static bool copy_chunked(const std::string& src, const std::string& dst,
                         uint32_t* sum_out) {
    std::ifstream in(src, std::ios::binary);
    std::ofstream out(dst, std::ios::binary);
    if (!in || !out) return false;
    char buf[8192];
    uint32_t sum = fnv1a(nullptr, 0);
    for (;;) {
        in.read(buf, sizeof(buf));
        const std::streamsize n = in.gcount();
        if (n > 0) {
            out.write(buf, n);
            sum = fnv1a(buf, static_cast<size_t>(n), sum);
        }
        if (in.eof()) break;
        if (in.fail() || !out) return false;
    }
    *sum_out = sum;
    return true;
}

// 计算整文件校验和（verify 用）
static bool file_checksum(const std::string& path, uint32_t* sum_out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char buf[8192];
    uint32_t sum = fnv1a(nullptr, 0);
    for (;;) {
        in.read(buf, sizeof(buf));
        const std::streamsize n = in.gcount();
        if (n > 0) sum = fnv1a(buf, static_cast<size_t>(n), sum);
        if (in.eof()) break;
        if (in.fail()) return false;
    }
    *sum_out = sum;
    return true;
}

static std::string hex(uint32_t v) {
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%08x", v);
    return buf;
}

static int run_selftest() {
    const std::string src = "/tmp/ph09_sol4_src.bin";
    const std::string dst = "/tmp/ph09_sol4_dst.bin";
    {
        std::ofstream out(src, std::ios::binary);
        std::mt19937 rng(7);
        char buf[8192];
        for (int i = 0; i < 32; ++i) {
            for (char& c : buf) c = static_cast<char>(rng() & 0xff);
            out.write(buf, sizeof(buf));
        }
    }
    uint32_t sum = 0;
    if (!copy_chunked(src, dst, &sum)) { std::cerr << "send failed\n"; return 1; }
    uint32_t got = 0;
    if (!file_checksum(dst, &got) || got != sum) {
        std::cerr << "verify mismatch\n";
        return 1;
    }
    std::cout << "send+verify OK checksum=0x" << hex(sum) << '\n';
    // 篡改一个字节 → verify 应失败
    {
        std::fstream f(dst, std::ios::in | std::ios::out | std::ios::binary);
        f.seekp(100);
        const char c = 'X';
        f.write(&c, 1);
    }
    if (!file_checksum(dst, &got) || got == sum) {
        std::cerr << "tamper detect failed\n";
        return 1;
    }
    std::cout << "tamper detected (checksum changed to 0x" << hex(got) << ") OK\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "selftest") return run_selftest();
    if (argc != 4) {
        std::cerr << "usage: ./sol-04 selftest | send <src> <dst> | verify <file> <checksum-hex>\n";
        return 1;
    }
    try {
        const std::string cmd = argv[1];
        if (cmd == "send") {
            uint32_t sum = 0;
            if (!copy_chunked(argv[2], argv[3], &sum)) {
                std::cerr << "send failed\n";
                return 1;
            }
            std::cout << "sent checksum=0x" << hex(sum) << '\n';
            return 0;
        }
        if (cmd == "verify") {
            uint32_t sum = 0, want = 0;
            if (!file_checksum(argv[2], &sum)) {
                std::cerr << "verify: cannot open " << argv[2] << '\n';
                return 1;
            }
            want = static_cast<uint32_t>(std::stoul(argv[3], nullptr, 16));
            if (sum != want) {
                std::cerr << "verify FAILED: got 0x" << hex(sum)
                          << " want 0x" << hex(want) << '\n';
                return 1;
            }
            std::cout << "verify OK 0x" << hex(sum) << '\n';
            return 0;
        }
        std::cerr << "unknown command: " << cmd << '\n';
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n';
        return 1;
    }
}
