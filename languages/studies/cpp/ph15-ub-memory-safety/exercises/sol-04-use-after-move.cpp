// sol-04-use-after-move.cpp —— 练习 4 参考实现：use-after-move 与 moved-from 使用纪律
// 练习 4 要求：识别“把 moved-from 对象当仍拥有数据使用”的 UB（解引用被移走的
//   unique_ptr），修复为安全写法；并说明 moved-from 对象“能做什么、不能做什么”
//   （覆盖 roadmap 学习内容「use-after-move 语义风险」）。
//
// 坏版本（有 bug，勿这样写；故意出错，须用 -fsanitize=undefined -fno-sanitize-recover=all
//   编译复现，勿裸跑）：
//   auto up = std::make_unique<int>(42);
//   auto moved = std::move(up);      // 所有权转移：up 保证为空（unique_ptr 指定语义）
//   std::printf("%d\n", *moved);
//   std::printf("%d\n", *up);        // UB: 解引用 moved-from 的空 unique_ptr
//
// 本机实测（坏版本，Apple clang 21.0.0，-O0 -g）：
//   UBSan：runtime error: reference binding to null pointer of type 'int'
//          （位于 libc++ unique_ptr.h 的 operator*），退出码 134；
//   去掉 UBSan 裸跑：Segmentation fault，退出码 139 —— 两种表现都是 UB 的合法形态。
//
// 修复思路（moved-from 使用纪律）：
//   1. move 后对象“合法但未指定”（[lib.types.movedfrom]）：可析构、可重新赋值、
//      可调用不依赖状态的操作；不可假设内容、不可当仍拥有数据使用；
//   2. unique_ptr 的 moved-from 状态是**指定的**——保证为空（get()==nullptr）；
//      需要“再用”就 reset 重建，使用前先判空；
//   3. 若只是借用（只读看两眼），在 move 之前完成；转移后只访问新持有者。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-04-use-after-move.cpp -o /tmp/ph15-sol-04
// 运行：    /tmp/ph15-sol-04
// 验证状态：已验证（两种编译器零警告、输出一致；+ASan+UBSan 复跑零报告）
#include <cstdio>
#include <memory>
#include <string>
#include <utility>

int main() {
    std::printf("[A] 坏版本实测（见文件头）：*up（moved-from）→ UBSan 报\n");
    std::printf("    reference binding to null pointer of type 'int'，退出码 134\n");

    std::printf("[B] 修复 1：使用前判空 / reset 重建 —— unique_ptr 的 moved-from 保证为空\n");
    {
        auto up = std::make_unique<int>(42);
        auto moved = std::move(up);
        std::printf("    moved-from up 为空: %s（标准指定，不是“碰巧”）\n",
                    up.get() == nullptr ? "是" : "否");
        if (up) {                          // 判空后再使用（不会走到：up 必为空）
            std::printf("    *up=%d\n", *up);
        }
        up = std::make_unique<int>(7);     // reset/重建后恢复可用
        std::printf("    重建后 *up=%d\n", *up);
        std::printf("    *moved=%d（新持有者正常使用）\n", *moved);
    }

    std::printf("[C] 修复 2：moved-from 对象只做三件事 —— 析构 / 重新赋值 / 状态无关调用\n");
    {
        std::string a = "payload-0123456789";
        std::string b = std::move(a);
        std::printf("    moved-from a.size()=%zu（实测 libc++ 置空；标准只说“未指定”）\n",
                    a.size());
        a = "reassigned";                  // 重新赋值合法
        std::printf("    重新赋值后 a=\"%s\"\n", a.c_str());
        std::printf("    b=\"%s\"\n", b.c_str());
    }

    std::printf("[D] 反直觉点：moved-from 不是“禁用对象”，但内容不可假设 ——\n");
    std::printf("    假设 moved-from 一定为空/一定不变 = 逻辑错误（多数实现置空，标准不保证）\n");
    return 0;
}
// 本机实测（两种编译器一致，零警告；+ASan+UBSan 零报告，退出码 0）：
//   [B] moved-from up 为空: 是；重建后 *up=7；*moved=42
//   [C] moved-from a.size()=0；重新赋值后 a="reassigned"；b="payload-0123456789"
