// ex06-fswalk.cpp —— std::filesystem 目录遍历：递归统计文件数/大小 + 复制演示
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex06-fswalk.cpp -o ex06
// 运行：
//   ./ex06 selftest               —— 自动验证：建测试目录树 → 遍历统计 → 复制
//   ./ex06 <dir>                  —— 手动模式：递归统计 <dir> 的文件数与总大小
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
namespace fs = std::filesystem;

struct TreeStats {
    std::size_t files = 0;
    std::size_t dirs = 0;
    std::uintmax_t bytes = 0;
};

// 递归遍历目录树统计；单条错误通过 error_code 容忍，不中断整体
static TreeStats scan_tree(const fs::path& root) {
    TreeStats st;
    std::error_code ec;
    for (fs::recursive_directory_iterator it(root, ec), end; it != end;
         it.increment(ec)) {
        if (ec) {                                   // 某个子目录不可读：跳过继续
            std::cerr << "warn: " << ec.message() << '\n';
            ec.clear();
            continue;
        }
        if (it->is_directory(ec)) {
            ++st.dirs;
        } else if (it->is_regular_file(ec)) {
            ++st.files;
            st.bytes += it->file_size(ec);
        }
    }
    return st;
}

// 把目录树复制到目标并逐文件校验存在性（error_code 版，容忍个别失败）
static bool copy_tree(const fs::path& src, const fs::path& dst) {
    std::error_code ec;
    fs::create_directories(dst, ec);
    if (ec) return false;
    for (fs::recursive_directory_iterator it(src, ec), end; it != end;
         it.increment(ec)) {
        if (ec) { ec.clear(); continue; }
        const fs::path rel = it->path().lexically_relative(src);
        const fs::path out = dst / rel;
        if (it->is_directory(ec)) {
            fs::create_directories(out, ec);
            if (ec) return false;
        } else if (it->is_regular_file(ec)) {
            fs::copy_file(it->path(), out,
                          fs::copy_options::overwrite_existing, ec);
            if (ec) return false;
        }
    }
    return true;
}

static int run_selftest() {
    const fs::path root = "/tmp/ph09_fswalk_src";
    const fs::path dst = "/tmp/ph09_fswalk_dst";
    fs::remove_all(root);                          // 清理上次残留
    fs::remove_all(dst);
    fs::create_directories(root / "sub" / "deep"); // 递归建多层目录
    { std::ofstream(root / "a.txt") << "hello\n"; }
    { std::ofstream(root / "sub" / "b.bin") << std::string(4096, 'x'); }
    { std::ofstream(root / "sub" / "deep" / "c.log") << "bye\n"; }

    const TreeStats st = scan_tree(root);
    std::cout << "scanned: files=" << st.files << " dirs=" << st.dirs
              << " bytes=" << st.bytes << '\n';
    if (st.files != 3 || st.dirs != 2) { std::cerr << "scan mismatch\n"; return 1; }

    if (!copy_tree(root, dst)) { std::cerr << "copy failed\n"; return 1; }
    const TreeStats st2 = scan_tree(dst);
    std::cout << "copied:  files=" << st2.files << " dirs=" << st2.dirs
              << " bytes=" << st2.bytes << '\n';
    if (st2.files != st.files || st2.dirs != st.dirs || st2.bytes != st.bytes) {
        std::cerr << "copy mismatch\n";
        return 1;
    }
    std::cout << "filesystem walk + copy OK\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "selftest") return run_selftest();
    if (argc != 2) {
        std::cerr << "usage: ./ex06 selftest | <dir>\n";
        return 1;
    }
    const TreeStats st = scan_tree(argv[1]);
    std::cout << argv[1] << ": files=" << st.files << " dirs=" << st.dirs
              << " bytes=" << st.bytes << '\n';
    return 0;
}
