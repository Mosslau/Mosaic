// Tenet 命令行入口（与 tenet-rs/src/main.rs、tenet-py/tenet/__main__.py 行为一致）。
//
//   tenet run <file>      # 解释执行 Tenet 源码
//   tenet codegen <file>  # 编译为 Go 源码（打印到 stdout）
//   tenet repl            # 交互式 REPL
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "codegen.hpp"
#include "error.hpp"
#include "interpreter.hpp"
#include "parser.hpp"
#include "repl.hpp"

using namespace tenet;

static void usage() {
    std::cerr << "用法:\n"
                 "  tenet run <file>     解释执行\n"
                 "  tenet codegen <file> 生成 Go 源码\n"
                 "  tenet repl           交互式 REPL\n";
    std::exit(2);
}

static std::string read_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "无法读取文件 " << path << "\n";
        std::exit(1);
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

int main(int argc, char** argv) {
    if (argc < 2) usage();
    std::string cmd = argv[1];

    if (cmd == "repl") {
        if (argc != 2) usage();
        repl_run();
        return 0;
    }

    if (cmd == "run" || cmd == "codegen") {
        if (argc != 3) usage();
        std::string src = read_file(argv[2]);
        try {
            Program program = Parser::parse(src);
            if (cmd == "run") {
                Interpreter::run(program);
            } else {
                std::cout << GoCodegen::generate(program);
            }
        } catch (const TenetError& e) {
            std::cerr << e.str() << "\n";
            return 1;
        }
        return 0;
    }

    usage();
}
