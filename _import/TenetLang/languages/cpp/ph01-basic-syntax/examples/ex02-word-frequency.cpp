// examples/ex02-word-frequency.cpp —— 词频统计：排序后按相邻相同词计数
// 来源：languages/cpp/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 2
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-word-frequency.cpp -o ex02
// 运行：./ex02
// 已验证：本环境编译零警告，输出 apple: 3 / banana: 2 / orange: 1
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

int main() {
    std::vector<std::string> words = {
        "apple", "banana", "apple", "orange", "banana", "apple"
    };

    std::sort(words.begin(), words.end());  // 相同词排序后相邻，只需一次线性扫描

    std::string current = words[0];
    int count = 1;
    for (size_t i = 1; i < words.size(); ++i) {
        if (words[i] == current) {
            ++count;
        } else {
            std::cout << current << ": " << count << '\n';
            current = words[i];
            count = 1;
        }
    }
    std::cout << current << ": " << count << '\n';  // 输出最后一组
    return 0;
}
