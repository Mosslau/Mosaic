// examples/ex05-coverage/grade.h —— 覆盖率演示的被测对象：多分支纯函数
// 分支越多，越适合演示「覆盖率报告告诉你哪条路没走到」。
#ifndef EX05_GRADE_H
#define EX05_GRADE_H

#include <stdexcept>

enum class Grade { fail, pass, good, excellent };

// 分数 → 等级；非法输入抛异常（E.2）
inline Grade classify(int score) {
    if (score < 0 || score > 100) {
        throw std::invalid_argument("score out of range");
    }
    if (score < 60) {
        return Grade::fail;
    }
    if (score < 80) {
        return Grade::pass;
    }
    if (score < 90) {
        return Grade::good;
    }
    return Grade::excellent;
}

#endif  // EX05_GRADE_H
