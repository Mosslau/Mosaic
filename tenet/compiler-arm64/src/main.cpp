// Tenet 编译器命令行入口（compiler-arm64：手写 AArch64 后端，不用 LLVM/clang）。
//
//   tenet build <file> [-o <out>]   编译为原生二进制
//   tenet run   <file>              编译并直接运行
//   tenet asm   <file>              打印生成的 arm64 汇编（调试）
//
// 管线：.tenet → 本编译器 → .s → 系统 as 汇编 → ld 链接 → 原生二进制
// 全链路零 LLVM、零 clang 做代码生成（as/ld 来自系统，即"手"）。

#include <cstdio>
#include <unistd.h>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "backend.hpp"
#include "error.hpp"
#include "parser.hpp"

using namespace tenet;

namespace {

void usage() {
    std::cerr << "用法:\n"
                 "  tenet build <file> [-o <out>]\n"
                 "  tenet run <file>\n"
                 "  tenet asm <file>\n";
    std::exit(2);
}

std::string read_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "无法读取文件 " << path << "\n";
        std::exit(1);
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

std::string sdk_path() {
    const char* e = std::getenv("TENET_SDK");
    if (e) return e;
    std::string out;
    FILE* pipe = popen("xcrun --show-sdk-path 2>/dev/null", "r");
    if (!pipe) return "";
    char buf[512];
    while (fgets(buf, sizeof(buf), pipe)) out += buf;
    pclose(pipe);
    // 去掉换行
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r')) out.pop_back();
    return out;
}

std::string temp_path(const std::string& suffix) {
    const char* tmp = std::getenv("TMPDIR");
    return std::string(tmp ? tmp : "/tmp") + "/tenet-arm64-" + std::to_string(::getpid()) + suffix;
}

void run_cmd(const std::string& cmd) {
    int rc = std::system(cmd.c_str());
    if (rc != 0) {
        throw TenetError("外部工具执行失败: " + cmd);
    }
}

/// 汇编 + 链接：as file.s → .o → ld → 可执行文件。
void assemble_link(const std::string& asm_path, const std::string& obj_path, const std::string& out) {
    const char* as = std::getenv("TENET_AS");
    const char* ld = std::getenv("TENET_LD");
    std::string as_bin = as ? as : "as";
    std::string ld_bin = ld ? ld : "ld";
    std::string sdk = sdk_path();
    if (sdk.empty()) {
        throw TenetError("找不到 SDK（需要 Xcode 命令行工具）；可用 TENET_SDK 指定");
    }
    run_cmd(as_bin + " " + asm_path + " -o " + obj_path);
    run_cmd(ld_bin + " " + obj_path + " -o " + out + " -lSystem -syslibroot " + sdk +
            " -e _main -arch arm64");
}

void build(const std::string& src_path, const std::string& out) {
    std::string src = read_file(src_path);
    auto program = Parser::parse(src);
    std::string asm_text = Backend::generate(program);

    std::string asm_path = temp_path(".s");
    std::string obj_path = temp_path(".o");
    {
        std::ofstream f(asm_path);
        f << asm_text;
    }
    try {
        assemble_link(asm_path, obj_path, out);
    } catch (...) {
        std::remove(asm_path.c_str());
        std::remove(obj_path.c_str());
        throw;
    }
    std::remove(asm_path.c_str());
    std::remove(obj_path.c_str());
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) usage();
    std::string cmd = argv[1];

    if (cmd == "asm") {
        if (argc != 3) usage();
        try {
            auto program = Parser::parse(read_file(argv[2]));
            std::cout << Backend::generate(program);
        } catch (const TenetError& e) {
            std::cerr << e.str() << "\n";
            return 1;
        }
        return 0;
    }

    if (cmd == "build") {
        if (argc < 3 || argc > 5) usage();
        std::string out = "a.out";
        for (int i = 2; i < argc - 1; ++i) {
            if (std::string(argv[i]) == "-o") out = argv[i + 1];
        }
        try {
            build(argv[2], out);
            std::cout << "已生成可执行文件: " << out << "\n";
        } catch (const TenetError& e) {
            std::cerr << e.str() << "\n";
            return 1;
        }
        return 0;
    }

    if (cmd == "run") {
        if (argc != 3) usage();
        std::string bin = temp_path("-run");
        try {
            build(argv[2], bin);
            int rc = std::system((bin + " ; exit $?").c_str());
            std::remove(bin.c_str());
            return rc;
        } catch (const TenetError& e) {
            std::cerr << e.str() << "\n";
            return 1;
        }
    }

    usage();
}
