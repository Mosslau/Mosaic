// sol-04-fix-dangling.cpp —— 练习 4 参考实现：改造返回悬空引用的代码
// 练习 4 要求：下列工厂函数返回 const&，实为悬空引用（返回绑定到临时对象的引用，
//   临时对象在 return 语句结束时销毁）。请改造为不悬空的接口并说明理由。
//
//   // 原始（有 bug，勿这样写）：
//   const std::string& config_path(const std::string& base) {
//       return base + "/config.json";   // 悬空：绑定到临时 string 的引用
//   }
//
// 本机实测（已验证，Apple clang 21.0.0）：
//   - 原始版本编译告警（-Wall -Wextra）：
//     warning: returning reference to local temporary object [-Wreturn-stack-address]
//   - 改造后（本文件）零警告，运行输出：
//     path = /etc/app/config.json
//     view = /etc/app/config.json
//   - 说明：view 是 string_view，借用自 path；path 存活期间安全
//
// 改造理由：
//   - 首选"按值返回"：std::string 是值语义，返回 prvalue 由 C++17 保证省略
//     直接构造到调用方，零拷贝零移动（见 ex03）——接口简单且不可能悬空
//   - 若调用方只需要"读"，可以再从返回值的字符串上取 string_view；
//     string_view 只借用不拥有，必须保证它引用的对象（返回值）还活着
//   - 不要改成"返回 std::string_view 的引用/值"来绕——视图不拥有数据，
//     数据源（临时 string）销毁后视图照样悬空，只是把问题藏得更深
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-04-fix-dangling.cpp -o /tmp/sol-04
// 运行：    /tmp/sol-04
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>

// 改造后：按值返回 prvalue，保证省略，零拷贝零移动，绝不悬空
std::string config_path(const std::string& base) {
    return base + "/config.json";
}

int main() {
    const std::string path = config_path("/etc/app");   // 值语义：path 拥有数据
    std::printf("path = %s\n", path.c_str());

    // 借用：从 path 上取视图，path 存活期间安全
    const std::string_view view = path;
    std::printf("view = %.*s\n", static_cast<int>(view.size()), view.data());

    // 反例说明（不要这样写）：view 的生命周期必须短于 path；
    // 若把 view 存起来、之后又修改/销毁 path，view 即悬空（见 ex05）
    return 0;
}
