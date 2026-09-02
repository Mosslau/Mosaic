// ex04-use-after-move.cpp —— use-after-move 语义：moved-from 状态“合法但未指定”
// 主题：C++11 移动语义引入后，被移动对象（moved-from）的语义由 [lib.types.movedfrom]
//       规定：**合法但未指定**（valid but unspecified）——可以安全析构、可以重新赋值、
//       可以调用不依赖状态的操作，但**不能假设其内容**。误用分两档：① 把 moved-from
//       对象当“仍拥有数据”使用（如解引用被移走的 unique_ptr）→ 真 UB（实测）；
//       ② 假设 moved-from 一定为空/一定不变 → 逻辑错误（多数实现为空，但标准不保证）。
//       unique_ptr 是少数 moved-from 状态被**指定**的类型：移走后保证为空（get()==nullptr）。
// 运行前提（故意出错变体，勿裸跑）：
//   -DEX04_DEREF_MOVED  必须用 c++ -std=c++20 -Wall -Wextra -O0 -g
//                       -fsanitize=undefined -fno-sanitize-recover=all 编译运行
//                       （解引用 moved-from 的 unique_ptr：UBSan 报 reference binding
//                         to null pointer；去掉 UBSan 裸跑实测 SIGSEGV 退出码 139）
// 默认（无 -D）编译零警告：打印 moved-from 语义对照（全部为定义行为），可任意运行。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20（libc++）
// 编译：    c++ -std=c++20 -Wall -Wextra ex04-use-after-move.cpp -o /tmp/ph15-ex04
// 运行：    /tmp/ph15-ex04
// 验证状态：已验证（默认零警告；变体报告实测记录于本文件底部注释）
#include <cstdio>
#include <memory>
#include <string>
#include <utility>

int main() {
#if defined(EX04_DEREF_MOVED)
    // 危险路径：把 moved-from 的 unique_ptr 当“仍拥有数据”解引用
    auto up = std::make_unique<int>(42);
    auto moved = std::move(up);            // 所有权转移：up 保证为空（unique_ptr 指定语义）
    std::printf("deref: up 是否为空（moved-from unique_ptr）: %s\n",
                up ? "否（异常！）" : "是");
    std::printf("deref: 解引用 moved-from 的 up ...\n");
    std::printf("deref: *up=%d\n", *up);   // UB: 解引用空指针（UBSan 在此中止）
#else
    // —— 语义对照（默认）：moved-from 对象能做什么、不能做什么 ——
    std::printf("[1] std::string 被移动后：合法但未指定（[lib.types.movedfrom]）\n");
    {
        std::string a = "payload-0123456789";
        std::string b = std::move(a);      // 数据移给 b
        // 合法：析构、重新赋值、调用不依赖状态的成员
        std::printf("    moved-from a: size=%zu（实测 libc++ 置空；标准只说“未指定”）\n", a.size());
        a = "reassigned";                  // 重新赋值合法 —— moved-from 不是“禁用对象”
        std::printf("    重新赋值后 a=\"%s\"\n", a.c_str());
    }
    std::printf("[2] 标准承诺 vs 实测：string 为空是 libc++ 的实现选择，不是标准承诺\n");
    std::printf("    标准只保证“有效但未指定”；程序若假设 moved-from 为空，换实现即错\n");
    std::printf("[3] unique_ptr 被移动后：状态是**指定的**——保证为空\n");
    {
        auto up = std::make_unique<int>(42);
        auto moved = std::move(up);
        std::printf("    moved-from up 为空（get()==nullptr）: %s\n",
                    up.get() == nullptr ? "是" : "否");
        std::printf("    moved 持有值: *moved=%d\n", *moved);
    }
    std::printf("[4] moved-from 使用纪律：移走后只做三件事——析构 / 重新赋值 /\n");
    std::printf("    不依赖状态的操作；需要“可再用”就用 unique_ptr 的 reset 重建\n");
    std::printf("    危险变体 -DEX04_DEREF_MOVED：解引用 moved-from unique_ptr（UB）\n");
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0；默认零警告，Homebrew clang 21.1.8 同）：
//   [默认] [1] moved-from a: size=0（libc++ 实测置空）→ 重新赋值 a="reassigned"
//          [3] moved-from up 为空: 是
//   [-DEX04_DEREF_MOVED + UBSan] 退出码 134：
//     runtime error: reference binding to null pointer of type 'int'
//     SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior .../unique_ptr.h:...
//   [-DEX04_DEREF_MOVED 裸跑（无 UBSan，-O0）] 退出码 139：Segmentation fault: 11
//   （moved-from string 实测 size=0 是 libc++ 行为——标准层面是“未指定”，
//     不得写成“标准保证为空”；unique_ptr 才是标准保证为空）
