// 交互式 REPL：逐行读取、执行、打印结果。
// 与 tenet-rs/src/repl.rs、tenet-py/tenet/repl.py 行为一致：
// - 花括号不闭合时继续读取下一行（简易多行支持）
// - 缺分号时自动补 `;` 重试（REPL 习惯）
// - 单条非 print 表达式 → 求值并回显
// - `exit` / `quit` 或 Ctrl-D 退出
// - 复用同一个 Interpreter 实例 → 跨行记住变量与函数
#pragma once

#include <iostream>
#include <string>

#include "ast.hpp"
#include "error.hpp"
#include "interpreter.hpp"
#include "parser.hpp"

namespace tenet {

/// 执行解析结果：单条非 print 表达式 → 求值回显；否则作为程序执行。
inline void run_parsed(Interpreter& interp, const Program& program) {
    if (program.stmts.size() == 1) {
        const StmtPtr& stmt = program.stmts[0];
        if (stmt->kind == Stmt::Kind::Expr) {
            const ExprPtr& e = stmt->expr;
            bool is_print = e->kind == Expr::Kind::Call && e->name == "print";
            if (!is_print) {
                Value v = interp.eval_expr(e);
                if (!is_nil(v)) {
                    std::cout << display(v) << "\n";
                }
                return;
            }
        }
    }
    interp.run_program(program);
}

/// 粗略判断花括号 / 括号 / 方括号是否配平（忽略字符串与注释内的括号）。
inline bool balanced(const std::string& src) {
    std::string stack;
    bool in_str = false;
    for (size_t i = 0; i < src.size(); ++i) {
        char c = src[i];
        if (in_str) {
            if (c == '\\') {
                ++i;  // 跳过转义的下一个字符
            } else if (c == '"') {
                in_str = false;
            }
            continue;
        }
        if (c == '"') {
            in_str = true;
        } else if (c == '(' || c == '{' || c == '[') {
            stack.push_back(c);
        } else if (c == ')' || c == '}' || c == ']') {
            char open = (c == ')') ? '(' : (c == '}') ? '{' : '[';
            if (stack.empty() || stack.back() != open) {
                return true;  // 配不上，交给 parser 报错
            }
            stack.pop_back();
        }
    }
    return !in_str && stack.empty();
}

inline void repl_run() {
    Interpreter interp;
    std::string buffer;

    std::cout << "\n🏛 Tenet REPL — 万语归宗，探语言之本源\n"
                 "输入 Tenet 语句，`exit` 或 Ctrl-D 退出。\n";

    while (true) {
        std::cout << (buffer.empty() ? "tenet> " : "     > ") << std::flush;
        std::string line;
        if (!std::getline(std::cin, line)) {
            std::cout << "\n";
            break;
        }
        // 去掉行尾 \r（Windows 管道输入）
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string trimmed = line;
        // trim
        size_t b = trimmed.find_first_not_of(" \t");
        size_t e = trimmed.find_last_not_of(" \t");
        trimmed = (b == std::string::npos) ? "" : trimmed.substr(b, e - b + 1);
        if (trimmed == "exit" || trimmed == "quit") break;
        buffer += line;
        buffer += "\n";

        // 括号未配平 → 继续收集输入
        if (!balanced(buffer)) continue;

        std::string src = buffer;
        buffer.clear();
        try {
            Program program = Parser::parse(src);
            run_parsed(interp, program);
        } catch (const TenetError& e) {
            // REPL 习惯不写分号：若错误只是「期望 `;` 但遇到 EOF」，补上分号重试
            int line_count = 1;
            for (char c : src) {
                if (c == '\n') ++line_count;
            }
            std::string rtrimmed = src;
            size_t le = rtrimmed.find_last_not_of(" \t\r\n");
            rtrimmed = (le == std::string::npos) ? "" : rtrimmed.substr(0, le + 1);
            if (e.message.find("`;`") != std::string::npos && e.pos.has_value()
                && e.pos->line >= line_count && !rtrimmed.empty()
                && rtrimmed.back() != ';') {
                try {
                    Program program = Parser::parse(src + ";");
                    run_parsed(interp, program);
                    continue;
                } catch (const TenetError&) {
                    // 补分号仍失败，报原始错误
                }
            }
            std::cerr << e.str() << "\n";
        }
    }
}

}  // namespace tenet
