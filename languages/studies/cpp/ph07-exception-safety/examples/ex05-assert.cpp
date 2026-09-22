// 来源：languages/cpp/ph07-exception-safety/07-exception-safety.md 第 6 章示例 5
// 说明：断言与防御式编程——assert / static_assert / 前置条件检查
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 examples/ex05-assert.cpp -o ex05
// 运行：./ex05
// 验证状态：已验证
#include <cassert>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>

static_assert(sizeof(int) >= 4, "int must be at least 32 bits");  // 编译期断言

class Config {
public:
    explicit Config(int max_connections) : max_connections_(max_connections) {
        if (max_connections <= 0)             // 前置条件：外部输入用异常（release 也生效）
            throw std::invalid_argument("max_connections must be positive");
    }
    int max_connections() const { return max_connections_; }
private:
    int max_connections_;
};

double safe_sqrt(double x) {
    assert(x >= 0.0);              // 前置条件：调用方保证（debug 检查）
    return std::sqrt(x);
}

int main() {
    std::cout << "sizeof(int)=" << sizeof(int) << "\n";
    try {
        Config c(0);               // 触发前置条件异常
    } catch (const std::invalid_argument& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    std::cout << "sqrt(4)=" << safe_sqrt(4.0) << "\n";
    // safe_sqrt(-1.0);            // debug 构建触发 assert 中止；NDEBUG 下是 UB
    std::vector<int> v{1, 2, 3};
    assert(v.size() == 3);         // 后置条件/不变式
    std::cout << "vector ok\n";
    return 0;
}
