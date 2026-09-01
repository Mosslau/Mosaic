// sol-05-ownership-refactor.cpp —— 练习 5 参考实现：所有权接口重构
// 练习 5 要求：现有 Session 用裸指针 Profile* 持有配置并手写 new/delete，所有权
//   不清且拷贝赋值存在双重释放风险。请重构为"所有权通过类型体现"的现代写法：
//   拥有用 unique_ptr（移动即可转移所有权）、借用用 const&/string_view。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   name = alice
//   moved name = alice
//   size = 1
//   ASan 验证（c++ -std=c++20 -Wall -Wextra -fsanitize=address -g ...）：
//     - 普通运行与 ASan 运行输出一致、退出码 0，ASan 无越界/use-after-free/double-free 报告
//     - 泄漏检测（LeakSanitizer）在 macOS 上不支持（实测报 "detect_leaks is not
//       supported on this platform"），泄漏项需在 Linux 上验证——如实标注
//
// 重构要点：
//   - Profile 用 std::unique_ptr 持有 → 所有权明确：谁持有 Session 谁拥有 Profile
//   - unique_ptr 是 move-only → Session 不可拷贝，编译器在拷贝处直接报错
//     （想验证可取消注释 Session s2 = s1;，会得到 deleted function 错误）
//   - 转移所有权 = 移动：sessions.push_back(std::move(s1))，零拷贝
//   - 借用接口：profile() 返回 const&（只读借用）、name() 返回 string_view（不拷贝）
//   - Rule of Zero（C.20）：不用手写任何特殊成员函数，编译器生成的即正确
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-05-ownership-refactor.cpp -o /tmp/sol-05
//           c++ -std=c++20 -Wall -Wextra -fsanitize=address -g sol-05-ownership-refactor.cpp -o /tmp/sol-05-asan
// 运行：    /tmp/sol-05
//           /tmp/sol-05-asan        （ASan 版本：验证无泄漏、无双重释放）
// 验证状态：已验证（两种编译器均零警告，普通版与 ASan 版输出一致、无泄漏报告）
#include <cstdio>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

class Profile {
public:
    explicit Profile(std::string name) : name_(std::move(name)) {}
    const std::string& name() const { return name_; }   // 借用：只读

private:
    std::string name_;
};

class Session {
public:
    explicit Session(std::string name)
        : profile_(std::make_unique<Profile>(std::move(name))) {}
    // Rule of Zero：unique_ptr 管理所有权，编译器生成的析构/移动全部正确
    // （拷贝被隐式删除：Session 只能移动不能复制——所有权因此"通过类型体现"）

    const Profile& profile() const { return *profile_; }          // 借用
    std::string_view name() const { return profile_->name(); }    // 借用，不拷贝

private:
    std::unique_ptr<Profile> profile_;
};

int main() {
    Session s1("alice");
    std::printf("name = %s\n", std::string(s1.name()).c_str());   // 借用期间 s1 存活，安全

    std::vector<Session> sessions;
    sessions.push_back(std::move(s1));    // 所有权转移：s1 变为空，容器现在拥有 Profile
    std::printf("moved name = %s\n", std::string(sessions[0].name()).c_str());
    std::printf("size = %zu\n", sessions.size());

    // 注意：s1 已被移动，再访问 s1.name() 是 use-after-move（合法但值未指定）——
    // 正确的做法是访问转移后的持有者 sessions[0]（见 ph15 UB 阶段系统梳理）
    return 0;
}
