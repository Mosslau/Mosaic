// sol-03-tidy.cpp —— 练习 3 参考实现：clang-tidy 静态检查后的"修复版"
// 练习 3 描述的反模式（下标循环 / 冗长迭代器 / NULL / 值拷贝循环，可自建 sloppy.cpp 复现），
// clang-tidy 一跑即现形；本文件是 --fix 自动修复（+ 人工微调）后的干净版本，
// 复检零警告。修复前的警告输出与命令见文件末尾注释。
// 验证环境：Apple clang 21（g++ 兼容），clang-tidy（Homebrew LLVM 21）
// 检查命令（对修复前代码）：clang-tidy sloppy.cpp \
//   -checks='-*,modernize-loop-convert,modernize-use-auto,modernize-use-nullptr,\
//   performance-for-range-copy' -- -std=c++20
// 自动修复：clang-tidy sloppy.cpp -checks='-*,modernize-loop-convert,modernize-use-auto,\
//   modernize-use-nullptr,performance-for-range-copy' --fix -- -std=c++20
// 复检：clang-tidy sol-03-tidy.cpp -checks='-*,modernize-loop-convert,modernize-use-auto,\
//   modernize-use-nullptr,performance-for-range-copy' -- -std=c++20  → 零警告
// 验证状态：已验证（复检零警告 + -Wall -Wextra 编译零警告 + 运行通过）
#include <string>
#include <vector>

int main() {
    std::vector<int> v{1, 2, 3};
    int total = 0;
    for (const int i : v) {          // 修复 1：下标循环 → range-based for
        total += i;
    }
    const auto it = v.begin();       // 修复 2：冗长迭代器类型 → auto
    total += *it;
    int* p = nullptr;                // 修复 3：NULL → nullptr（ES.47）
    (void)p;
    const std::vector<std::string> names{"a", "bb"};
    for (const std::string& s : names) {   // 修复 4：值拷贝 → const&（F.16）
        total += static_cast<int>(s.size());
    }
    return total == 10 ? 0 : 1;   // 1+2+3（v）+ 1（*it）+ 1+2（names 长度）= 10
}

// 修复前的 4 条警告（本机实测，已验证）：
//   sloppy.cpp:7:5: warning: use range-based for loop instead [modernize-loop-convert]
//   sloppy.cpp:10:5: warning: use auto when declaring iterators [modernize-use-auto]
//   sloppy.cpp:12:14: warning: use nullptr [modernize-use-nullptr]
//   sloppy.cpp:15:28: warning: the loop variable's type is not a reference type;
//                          this creates a copy in each iteration; consider making
//                          this a reference [performance-for-range-copy]
// --fix 自动改写后复检零警告；再以 -std=c++20 -Wall -Wextra 编译零警告。
