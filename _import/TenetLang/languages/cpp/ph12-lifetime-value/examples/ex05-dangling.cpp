// ex05-dangling.cpp —— 故意出错：返回局部对象/临时对象的引用与视图（悬空引用）
// 主题：悬空引用是"能编译、能运行、结果随机"的 UB——编译器告警是第一道防线，
//       ASan 是运行期防线。本文件默认编译零警告（危险代码被宏关闭）；
//       定义 PH12_DANGLING 后，危险函数被编译并调用，产生 3 条预期告警，
//       ASan 可在运行期抓出 stack-use-after-return。
// 运行前提（危险路径）：必须用 -fsanitize=address 编译，并用
//       ASAN_OPTIONS=detect_stack_use_after_return=1 运行——macOS 的 ASan 默认
//       不检测 use-after-return（实测默认运行时程序"看似正常"直接通过，不报错），
//       必须显式开启该选项才能抓到。普通编译裸跑属于 UB，结果不可预期，勿依赖。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex05-dangling.cpp -o /tmp/ex05          （零警告，安全路径）
//           c++ -std=c++20 -Wall -Wextra -DPH12_DANGLING -fsanitize=address -g \
//                ex05-dangling.cpp -o /tmp/ex05-danger                             （预期 3 条告警）
// 运行：    /tmp/ex05
//           ASAN_OPTIONS=detect_stack_use_after_return=1 /tmp/ex05-danger          （ASan 报错退出）
// 验证状态：已验证（告警文本与 ASan 输出实测记录于文件底部与 examples/README.md）
#include <cstdio>
#include <string>
#include <string_view>

#if defined(PH12_DANGLING)
// 危险函数 1：返回局部对象的引用 —— F.43 明令禁止
const std::string& bad_local() {
    std::string s = "local-dangling";
    return s;                       // 告警：reference to stack memory ... returned [-Wreturn-stack-address]
}

// 危险函数 2：返回绑定到临时对象的引用 —— 临时对象在 return 语句结束时销毁
const std::string& bad_temp() {
    return std::string("temp-dangling");   // 告警：returning reference to local temporary object [-Wreturn-stack-address]
}

// 危险函数 3：返回局部对象的 string_view —— 隐式转换藏起"借用"关系
std::string_view bad_view() {
    std::string s = "view-dangling";
    return s;                       // 告警：address of stack memory ... returned [-Wreturn-stack-address]
}
#endif

int main() {
#if defined(PH12_DANGLING)
    const std::string& r1 = bad_local();
    const std::string& r2 = bad_temp();
    std::string_view v3 = bad_view();
    std::printf("r1=%s r2=%s v3=%.*s\n",
                r1.c_str(), r2.c_str(), static_cast<int>(v3.size()), v3.data());
    // ↑ 对已销毁对象做读取：stack-use-after-return（ASan 抓取点）
#else
    std::printf("default build：危险代码未启用（本文件零警告）。\n");
    std::printf("复现告警与 ASan 诊断：\n");
    std::printf("  c++ -std=c++20 -Wall -Wextra -DPH12_DANGLING -fsanitize=address -g ex05-dangling.cpp -o /tmp/ex05-danger\n");
    std::printf("  ASAN_OPTIONS=detect_stack_use_after_return=1 /tmp/ex05-danger\n");
    std::printf("安全写法见 ex02（const& 延长的合法边界）与 ex06（借用式接口）。\n");
#endif
    return 0;
}
// 实测记录（已验证，Apple clang 21.0.0）：
// ① 危险路径编译告警（-DPH12_DANGLING，共 3 条，编译退出码 0）：
//   ex05-dangling.cpp:25:12: warning: reference to stack memory associated with local variable 's' returned [-Wreturn-stack-address]
//   ex05-dangling.cpp:30:12: warning: returning reference to local temporary object [-Wreturn-stack-address]
//   ex05-dangling.cpp:36:12: warning: address of stack memory associated with local variable 's' returned [-Wreturn-stack-address]
// ② ASan 运行（ASAN_OPTIONS=detect_stack_use_after_return=1）：
//   ERROR: AddressSanitizer: stack-use-after-return on address ...
//   READ of size 1 at ... thread T0
//   SUMMARY: AddressSanitizer: stack-use-after-return ... in basic_string<...>::__is_long() const
//   （macOS 默认不开 use-after-return 检测；未设该选项时程序"看似正常"直接通过——这正是悬空引用的危险所在）
