// ex03-greeter.h —— pybind11 示例的 C++ 核心类（纯 C++，不经 C 包装层，直接绑类）
// 验证状态：未在本环境验证（pybind11 未 pip 安装）；代码与 pybind11 文档 API 一致
// 教学点：与 ex01 的 C 包装层对照——这里没有 opaque/错误码，类本身跨进 Python，
//         靠 pybind11 翻译类型与异常。同一份 C++ 类，ex01 走 C ABI、本示例走绑定。
#ifndef EX03_GREETER_H
#define EX03_GREETER_H

#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace greeter {

class greeter {
public:
    explicit greeter(std::string prefix) : prefix_(std::move(prefix)) {}

    // 输入校验失败直接抛异常：pybind11 会自动翻译成 Python ValueError
    std::string greet(const std::string& name) const {
        if (name.empty()) {
            throw std::invalid_argument("name must not be empty");
        }
        return prefix_ + ", " + name + "!";
    }

    // 返回 vector<string>：<pybind11/stl.h> 自动转换 list[str]
    std::vector<std::string> shout_all(const std::vector<std::string>& names) const {
        std::vector<std::string> out;
        out.reserve(names.size());
        for (const auto& n : names) {
            out.push_back(greet(n) + " (shout)");
        }
        return out;
    }

private:
    std::string prefix_;
};

}  // namespace greeter

#endif  // EX03_GREETER_H
