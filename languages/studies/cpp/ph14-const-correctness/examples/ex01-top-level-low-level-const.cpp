// ex01-top-level-low-level-const.cpp —— 顶层 const 与底层 const：const 的"层"是类型的一部分
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex01-top-level-low-level-const.cpp -o /tmp/ph14-ex01
// 运行：/tmp/ph14-ex01
#include <cstdio>
#include <type_traits>

// 顶层 const（top-level const）：作用于"对象本身"（const int、int* const、const 引用）
// 底层 const（low-level const）：作用于"指针/引用指向的对象"（const int*、const int&）
int main() {
    std::printf("[1] 顶层 const：对象本身不可变\n");
    const int x = 42;
    // x = 43;   // 编译错误：只读变量不可赋值（顶层 const 由编译器强制执行）
    std::printf("  const int x = 42;（x=%d，本身只读）\n", x);

    std::printf("[2] 底层 const：指向的对象不可通过该指针修改\n");
    int value = 7;
    const int* p = &value;      // 底层 const：*p 只读；但 value 本身非 const
    std::printf("  const int* p 指向非 const 的 value=%d（*p 只读）\n", *p);
    value = 8;                  // 对象本身非 const，别处照改
    std::printf("  value 被别处改为 %d，通过 p 读到 %d（只读路径看到变化）\n", value, *p);

    std::printf("[3] 指针自身的顶层 const：int* const\n");
    int a = 1;
    int* const q = &a;          // 顶层 const：q 本身不可改指向
    *q = 10;                    // 但 *q 可改（指向的对象非 const）
    // int b = 2; q = &b;       // 编译错误：q 是 const 指针，不能改指向
    std::printf("  int* const q：*q=%d（指针只读、指向的对象可写）\n", *q);

    std::printf("[4] 拷贝时顶层 const 脱落、底层 const 保留\n");
    const int cx = 5;
    auto copied = cx;           // copied 是 int：顶层 const 在拷贝/推导中被忽略
    static_assert(std::is_same_v<decltype(copied), int>);
    std::printf("  auto copied = cx 推导为 int（顶层 const 脱落）\n");
    const int* cp = &value;
    auto cp2 = cp;              // cp2 是 const int*：底层 const 保留
    static_assert(std::is_same_v<decltype(cp2), const int*>);
    std::printf("  auto cp2 = cp 推导为 const int*（底层 const 保留）\n");

    std::printf("[5] 转换方向：非 const → const 安全（收窄权限）；反向禁止\n");
    static_assert(std::is_convertible_v<int*, const int*>);   // 允许：读权限变小
    static_assert(!std::is_convertible_v<const int*, int*>);  // 禁止：读权限变大（需 const_cast）
    std::printf("  int* → const int* 允许（编译期特征 1）；const int* → int* 禁止（特征 0）\n");

    std::printf("[6] 函数参数：顶层 const 不影响函数类型（重载决议忽略它）\n");
    static_assert(std::is_same_v<void(int), void(const int)>);  // 参数顶层 const 不进函数类型
    std::printf("  void f(const int) 与 void f(int) 是同一个函数——不能靠它重载\n");
    return 0;
}
