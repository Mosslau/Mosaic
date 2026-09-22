// 来源：06-modern-cpp.md 第 6 章示例 4 —— std::variant 建模多种状态（设备状态 / 消息类型）
// 一句话说明：variant 类型安全建模 Running/Faulted/Offline 三态；holds_alternative + get
//             安全访问，std::visit + if constexpr 统一处理当前活跃分支。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex04-variant-state.cpp -o ex04-variant-state
// 运行：./ex04-variant-state
// 验证状态：已验证
#include <iostream>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

// 设备状态：运行中（带读数）/ 故障（带错误码）/ 离线
struct Running { double value; };
struct Faulted { int error_code; std::string message; };
struct Offline {};
using DeviceState = std::variant<Running, Faulted, Offline>;

std::string describe(const DeviceState& s) {
    if (std::holds_alternative<Running>(s))
        return "running, value=" + std::to_string(std::get<Running>(s).value);
    if (std::holds_alternative<Faulted>(s)) {
        const auto& f = std::get<Faulted>(s);
        return "fault " + std::to_string(f.error_code) + ": " + f.message;
    }
    return "offline";
}

int main() {
    std::vector<DeviceState> states = {
        Running{36.5}, Faulted{503, "sensor timeout"}, Offline{},
    };
    for (const auto& s : states) std::cout << describe(s) << "\n";

    // std::visit：对当前活跃分支统一处理（与 if constexpr 结合）
    std::visit([](const auto& s) {
        using T = std::decay_t<decltype(s)>;
        if constexpr (std::is_same_v<T, Running>)
            std::cout << "[visit] running value=" << s.value << "\n";
        else if constexpr (std::is_same_v<T, Faulted>)
            std::cout << "[visit] fault code=" << s.error_code << "\n";
        else
            std::cout << "[visit] offline\n";
    }, states[1]);

    std::cout << "index of Faulted = " << states[1].index() << "\n"; // 1
    return 0;
}
