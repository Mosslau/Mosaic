// examples/ex01-calculator.h —— 被测对象：一个刻意简单的计算器（对应 roadmap 示例）
// 接口设计要点：可测试性从接口开始——纯函数/小类最容易测（F.8 纯函数优先）。
#ifndef EX01_CALCULATOR_H
#define EX01_CALCULATOR_H

#include <stdexcept>

class Calculator {
public:
    static int add(int a, int b) { return a + b; }

    static int divide(int a, int b) {
        if (b == 0) {
            throw std::invalid_argument("divide by zero");  // E.2：用异常报告失败
        }
        return a / b;
    }
};

#endif  // EX01_CALCULATOR_H
