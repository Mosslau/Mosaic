// main.cpp —— 文件同步工具 CLI 入口 + 自测
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：make（或 c++ -std=c++20 -Wall -Wextra main.cpp file_sync.cpp checksum.cpp -o file_sync）
// 运行：
//   ./file_sync <src> <dst>   —— 把 src 目录同步到 dst（增量：未变化跳过）
//   ./file_sync --selftest    —— 自动验证：建测试树 → 同步 → 校验 → 再同步全跳过
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

#include "checksum.h"
#include "file_sync.h"

namespace fs = std::filesystem;

// 自测：在 /tmp 建测试目录树 → 同步 → 校验 → 第二次同步应全跳过
static int run_selftest() {
    const fs::path root = "/tmp/ph09_filesync_test";
    const fs::path dst = "/tmp/ph09_filesync_dst";
    fs::remove_all(root);
    fs::remove_all(dst);
    fs::create_directories(root / "sub" / "deep");
    { std::ofstream(root / "a.txt") << "hello sync\n"; }
    { std::ofstream(root / "sub" / "b.bin") << std::string(65536, 'B'); }
    { std::ofstream(root / "sub" / "deep" / "c.log") << "bye\n"; }

    std::string err;
    auto st1 = filesync::sync_tree(root, dst, &err);
    std::cout << "first sync: scanned=" << st1.scanned
              << " copied=" << st1.copied << " skipped=" << st1.skipped
              << " failed=" << st1.failed << " bytes=" << st1.copied_bytes
              << '\n';
    if (!err.empty()) { std::cerr << "error: " << err << '\n'; return 1; }
    if (st1.scanned != 3 || st1.copied != 3 || st1.failed != 0) {
        std::cerr << "first sync mismatch\n";
        return 1;
    }

    auto st2 = filesync::sync_tree(root, dst, &err);
    std::cout << "second sync: scanned=" << st2.scanned
              << " copied=" << st2.copied << " skipped=" << st2.skipped
              << " failed=" << st2.failed << '\n';
    if (!err.empty()) { std::cerr << "error: " << err << '\n'; return 1; }
    if (st2.copied != 0 || st2.skipped != 3 || st2.failed != 0) {
        std::cerr << "second sync should be all-skip\n";
        return 1;
    }

    // 篡改目标文件后重同步应重新复制
    {
        std::fstream f(dst / "a.txt", std::ios::in | std::ios::out);
        f.seekp(0);
        const char c = 'X';
        f.write(&c, 1);
    }
    auto st3 = filesync::sync_tree(root, dst, &err);
    std::cout << "third sync (tampered): copied=" << st3.copied
              << " skipped=" << st3.skipped << '\n';
    if (st3.copied != 1) {
        std::cerr << "tamper resync failed\n";
        return 1;
    }
    std::cout << "selftest OK\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--selftest") return run_selftest();
    if (argc != 3) {
        std::cerr << "usage: ./file_sync <src> <dst> | ./file_sync --selftest\n";
        return 1;
    }
    std::string err;
    const auto st = filesync::sync_tree(argv[1], argv[2], &err);
    std::cout << "scanned=" << st.scanned << " copied=" << st.copied
              << " skipped=" << st.skipped << " failed=" << st.failed
              << " bytes=" << st.copied_bytes << '\n';
    if (!err.empty()) {
        std::cerr << "error: " << err << '\n';
        return 1;
    }
    return st.failed == 0 ? 0 : 1;
}
