// Tenet 编译器命令行入口（C++17 版，调用 LLVM 后端库而非 clang 驱动）。
//
//   tenet build <file> [-o <out>]   编译为原生二进制
//   tenet run   <file>              编译并直接运行
//   tenet ir    <file>              打印 LLVM IR（调试）
//
// 后端：LLVM C++ API 进程内构建 IR → TargetMachine 产出对象文件 →
// 系统链接器（cc）链接 runtime → 原生二进制（与 rustc 相同的模型）。

#include <cstdio>
#include <unistd.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "llvm/TargetParser/Triple.h"
#include "llvm/CodeGen/TargetPassConfig.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Verifier.h"
#include "llvm/MC/TargetRegistry.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/TargetParser/Host.h"
#include "llvm/Support/TargetSelect.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Target/TargetMachine.h"
#include "llvm/Target/TargetOptions.h"

#include "ast.hpp"
#include "codegen.hpp"
#include "error.hpp"
#include "parser.hpp"

using namespace tenet;

namespace tenet {

void Codegen::emit_object(llvm::Module& mod, const std::string& obj_path) {
    // 初始化 LLVM 后端（TargetMachine / MC / 汇编器）
    llvm::InitializeAllTargetInfos();
    llvm::InitializeAllTargets();
    llvm::InitializeAllTargetMCs();
    llvm::InitializeAllAsmParsers();
    llvm::InitializeAllAsmPrinters();

    std::string triple = llvm::sys::getDefaultTargetTriple();
    mod.setTargetTriple(llvm::Triple(triple));

    std::string err;
    const llvm::Target* target = llvm::TargetRegistry::lookupTarget(triple, err);
    if (!target) throw TenetError("LLVM 目标查找失败: " + err);

    auto options = llvm::TargetOptions();
    auto rm = std::optional<llvm::Reloc::Model>(llvm::Reloc::PIC_);
    auto tm = std::unique_ptr<llvm::TargetMachine>(
        target->createTargetMachine(triple, "generic", "", options, rm));
    mod.setDataLayout(tm->createDataLayout());

    // IR 验证
    std::string verr;
    llvm::raw_string_ostream vso(verr);
    if (llvm::verifyModule(mod, &vso)) {
        throw TenetError("IR 验证失败: " + verr);
    }

    // LLVM 库进程内完成 IR → 机器码（对象文件）
    std::error_code ec;
    llvm::raw_fd_ostream out(obj_path, ec, llvm::sys::fs::OF_None);
    if (ec) throw TenetError("无法写入对象文件: " + ec.message());
    llvm::legacy::PassManager pm;
    if (tm->addPassesToEmitFile(pm, out, nullptr, llvm::CodeGenFileType::ObjectFile)) {
        throw TenetError("LLVM 后端不支持对象文件输出");
    }
    pm.run(mod);
    out.flush();
}

}  // namespace tenet

// ---- CLI ----

namespace {

const char* RUNTIME_C = R"(
#include <stdlib.h>
#include <string.h>
char* tenet_concat(const char* a, const char* b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = malloc(la + lb + 1);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}
int tenet_strcmp(const char* a, const char* b) { return strcmp(a, b); }
)";

void usage() {
    std::cerr << "用法:\n"
                 "  tenet build <file> [-o <out>]\n"
                 "  tenet run <file>\n"
                 "  tenet ir <file>\n";
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

void write_temp(const std::string& name, const std::string& content, std::string& out_path) {
    out_path = std::string(std::getenv("TMPDIR") ? std::getenv("TMPDIR") : "/tmp") + "/tenet-cpp-"
               + std::to_string(::getpid()) + "-" + name;
    std::ofstream out(out_path);
    out << content;
}

std::string cc_bin() {
    const char* e = std::getenv("TENET_CC");
    return e ? std::string(e) : std::string("cc");
}

/// 最后一步：系统链接器把对象文件 + runtime 链接成可执行文件
/// （LLVM 库已完成 IR→机器码；链接与 rustc 一样交给系统链接器）。
void link(const std::string& obj_path, const std::string& runtime_path, const std::string& out) {
    std::string cmd = cc_bin() + " " + obj_path + " " + runtime_path + " -o " + out;
    int rc = std::system(cmd.c_str());
    if (rc != 0) {
        throw TenetError("链接失败（系统链接器 " + cc_bin() + "）");
    }
}

void build(const std::string& src_path, const std::string& out) {
    std::string src = read_file(src_path);
    auto program = Parser::parse(src);
    auto compiled = Codegen::compile(program);
    auto& mod = *compiled.mod;

    std::string obj_path, runtime_path;
    write_temp("out.o", "", obj_path);
    write_temp("runtime.c", RUNTIME_C, runtime_path);
    try {
        Codegen::emit_object(mod, obj_path);
        link(obj_path, runtime_path, out);
    } catch (...) {
        std::remove(obj_path.c_str());
        std::remove(runtime_path.c_str());
        throw;
    }
    std::remove(obj_path.c_str());
    std::remove(runtime_path.c_str());
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) usage();
    std::string cmd = argv[1];

    if (cmd == "ir") {
        if (argc != 3) usage();
        try {
            auto program = Parser::parse(read_file(argv[2]));
            auto compiled = Codegen::compile(program);
            compiled.mod->print(llvm::errs(), nullptr);
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
        std::string bin = std::string(std::getenv("TMPDIR") ? std::getenv("TMPDIR") : "/tmp")
                          + "/tenet-cpp-run-" + std::to_string(::getpid());
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
