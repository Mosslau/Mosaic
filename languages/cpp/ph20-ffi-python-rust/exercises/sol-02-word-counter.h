// sol-02-word-counter.h —— 练习 2 C++ 核心类：纯 C++，异常随便用
// 验证状态：未在本环境验证（pybind11 未 pip 安装；代码与 pybind11 文档 API 一致）
#ifndef SOL02_WORD_COUNTER_H
#define SOL02_WORD_COUNTER_H

#include <algorithm>
#include <map>
#include <stdexcept>
#include <string>

namespace sol02 {

class word_counter {
public:
    void add(const std::string& word) {
        if (word.empty()) {
            throw std::invalid_argument("word must not be empty");  // → Python ValueError
        }
        ++counts_[word];
    }

    std::size_t total() const {
        std::size_t n = 0;
        for (const auto& [word, c] : counts_) n += c;
        return n;
    }

    std::size_t distinct() const { return counts_.size(); }

    // 返回 string：pybind11 自动转成 Python str（<pybind11/stl.h>）
    std::string most_common() const {
        if (counts_.empty()) {
            throw std::runtime_error("no words yet");  // → Python RuntimeError
        }
        const auto it = std::max_element(
            counts_.begin(), counts_.end(),
            [](const auto& a, const auto& b) { return a.second < b.second; });
        return it->first;
    }

private:
    std::map<std::string, std::size_t> counts_;  // Rule of Zero：标准库成员管内存
};

}  // namespace sol02

#endif  // SOL02_WORD_COUNTER_H
