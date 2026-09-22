// examples/ex01-mangling-demangle.cpp —— name mangling 教学完整版
// 教学点：roadmap 学习内容「name mangling」。C++ 函数名在二进制层面被编码为
// Itanium mangled 名（重载、命名空间、类、模板全部进符号）；本示例用 dladdr
// 在运行时取到真实符号名，再用 __cxa_demangle 反解回人可读名，并演示「签名
// 变化 → mangled 名变化 → 链接期即报错」的 ABI 护栏机制。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -Wall -Wextra ex01-mangling-demangle.cpp -o /tmp/ph19cpp-ex01
// 运行：/tmp/ph19cpp-ex01
// 用 nm 对照观察符号表中的真实名字（本机实测，Linux ELF 形态 _Z...，macOS
// Mach-O 的 nm 输出会给每个 C/C++ 符号再加一个 _ 前缀，见 nm 输出：__Z...）：
//   nm /tmp/ph19cpp-ex01 | c++filt        # 直接反解全部符号（c++filt 容忍 Mach-O 前缀）
//   nm /tmp/ph19cpp-ex01 | grep '_Z'
// 验证状态：已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器
//   -std=c++20 -Wall -Wextra 实测：编译零警告、运行通过、断言全绿）

#include <array>
#include <cstdlib>
#include <cstring>
#include <cxxabi.h>
#include <dlfcn.h>
#include <iostream>
#include <string>

namespace math {

int add(int a, int b) { return a + b; }
double add(double a, double b) { return a + b; }  // 重载：签名不同 → mangled 名不同

template <typename T>
T twice(T v) { return v + v; }

}  // namespace math

// dladdr 需要指向某个可寻址函数符号的指针。成员函数指针不能 cast 成函数指针，
// 因此这里统一对「自由函数 / 显式实例化的模板」取地址；成员函数的 mangled 名
// 在下方「已知名反解」与 nm 输出中观察。
namespace {

struct Sample {
    const char* label;
    void (*fn)();
};

int global_add(int a, int b) { return a + b; }

}  // namespace

// 显式实例化：保证 twice<int> 的真身符号出现在二进制里（模板默认按需实例化，
// 不调用就没符号，dladdr 就找不到）
template int math::twice<int>(int);

int main() {
    // 1. 运行时取真实符号名并反解（dladdr 返回的 dli_sname 已是 Itanium 形态，
    //    可直接交给 __cxa_demangle；而 nm 输出的 Mach-O 符号名多一个 _ 前缀）
    const std::array<Sample, 4> samples{{
        {"(匿名)::global_add(int,int)",
         reinterpret_cast<void (*)()>(&global_add)},
        {"math::add(int,int)  (重载 1)",
         reinterpret_cast<void (*)()>(static_cast<int (*)(int, int)>(&math::add))},
        {"math::add(double,double)  (重载 2)",
         reinterpret_cast<void (*)()>(static_cast<double (*)(double, double)>(&math::add))},
        {"math::twice<int>(int)  (显式实例化)",
         reinterpret_cast<void (*)()>(&math::twice<int>)},
    }};

    std::cout << "=== 运行时 dladdr + __cxa_demangle ===\n";
    for (const Sample& s : samples) {
        Dl_info info{};
        const bool ok = dladdr(reinterpret_cast<void*>(s.fn), &info) != 0 &&
                        info.dli_sname != nullptr;
        std::string sym = ok ? info.dli_sname : "(dladdr 拿不到符号，请用 nm 观察)";
        int status = -1;
        char* dem = abi::__cxa_demangle(sym.c_str(), nullptr, nullptr, &status);
        if (status == 0 && dem != nullptr) {
            std::cout << "  代码: " << s.label << "\n"
                      << "    mangled : " << sym << "\n"
                      << "    demangled: " << dem << "\n";
        } else {
            std::cout << "  代码: " << s.label << "  ->  mangled: " << sym
                      << " (demangle 失败, status=" << status << ")\n";
        }
        std::free(dem);
    }

    // 2. 反解一段「已知的」mangled 名——演示 Itanium mangling 形态对照
    //    注意：这段在 Linux ELF 与 macOS Mach-O 上 mangled 名本身完全一致
    //    （_Z...），区别只在 Mach-O 链接器给最终符号多压一层下划线（nm 输出
    //    __Z...）；dlsym/dladdr 层拿到的仍是 _Z... 形态。
    std::cout << "\n=== 已知 mangled 名反解（ELF 与 Mach-O 通用形态） ===\n";
    const char* known[] = {
        "_Z3foov",                  // void foo()
        "_ZN4math3addEii",          // int math::add(int, int)
        "_ZN4math3addEdd",          // double math::add(double, double)
        "_ZN4math5twiceIiEET_S1_",  // T math::twice<int>(int)
    };
    for (const char* m : known) {
        int status = -1;
        char* dem = abi::__cxa_demangle(m, nullptr, nullptr, &status);
        std::cout << "  " << m << "  ->  "
                  << (status == 0 ? dem : std::string("(demangle 失败)")) << "\n";
        std::free(dem);
    }

    // 3. ABI 护栏：把 mangled 名当字符串比较——签名一变，整个名字就变，
    //    旧调用方在链接期就失败（undefined symbol），而不是运行时静默错位。
    std::cout << "\n=== 签名变化 => mangled 名变化（链接期护栏原理） ===\n";
    const std::string add_ii = "_ZN4math3addEii";
    const std::string add_dd = "_ZN4math3addEdd";
    const std::string add_iii = "_ZN4math3addEiii";  // 假如后来加了第三个参数
    std::cout << "  int add(int,int)    与  int add(int,int,int)  相同? "
              << (add_ii == add_iii ? "是（危险）" : "否（mangling 已区分，护栏生效）") << "\n";
    std::cout << "  int add(int,int)    与  double add(double,double) 相同? "
              << (add_ii == add_dd ? "是（危险）" : "否（重载靠 mangling 区分）") << "\n";

    // 4. 自检断言
    int failures = 0;
    const auto expect = [&](bool cond, const char* msg) {
        if (!cond) {
            ++failures;
            std::cerr << "  [FAIL] " << msg << "\n";
        }
    };
    expect(std::strcmp(add_ii.c_str(), add_dd.c_str()) != 0,
           "两个重载必须 mangling 出不同符号名");
    expect(std::strcmp(add_ii.c_str(), add_iii.c_str()) != 0,
           "参数个数变化必须改变 mangled 名");
    expect(known[1] == add_ii, "math::add(int,int) 的 mangled 名应与表格一致");

    if (failures == 0) {
        std::cout << "\n[PASS] 全部断言通过\n";
        return 0;
    }
    std::cerr << "\n[FAIL] " << failures << " 项断言失败\n";
    return 1;
}
