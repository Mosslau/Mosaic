// sol-02-asan.cpp —— 练习 2 参考实现：堆越界 + ASan 定位
// 本文件是"故意出错的参考实现"：演示"写 bug → ASan 定位 → 修复"的完整过程。
// 教学性故意出错：循环条件 i <= n 应为 i < n（越界写 p[n]）；裸 new/delete 仅为
// 制造堆越界场景（R.11 在非教学代码中应避免）。修复方法见文件末尾注释。
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 普通编译（能通过，但掩盖问题）：c++ -std=c++20 -Wall -Wextra sol-02-asan.cpp -o sol-02
// ASan 编译：c++ -std=c++20 -g -fsanitize=address -fno-omit-frame-pointer \
//              sol-02-asan.cpp -o sol-02-asan
// ASan 运行：./sol-02-asan → 报 heap-buffer-overflow（WRITE of size 4，位于 main）
// 修复后验证：把循环条件改为 i < n 后，./sol-02-asan 输出 p[3]=9 且退出码 0
// 验证状态：已验证（普通编译零警告；ASan 运行报 heap-buffer-overflow；
//           本机沙箱环境外部符号化器无法启动，报告为地址+函数偏移形式，见下）
#include <cstdio>

static int* make_ints(int n) {
    return new int[n];   // 裸 new：教学性故意（见文件头注释）
}

int main() {
    const int n = 4;
    int* p = make_ints(n);
    for (int i = 0; i <= n; ++i) {   // 越界：i == n 时写 p[n]，堆上第 n+1 个 int
        p[i] = i * i;
    }
    std::printf("p[3]=%d\n", p[3]);
    delete[] p;                       // 裸 delete：教学性故意
    return 0;
}

// 本机实测 ASan 报告要点（已验证，未修符号化版）：
//   ERROR: AddressSanitizer: heap-buffer-overflow on address ...
//   WRITE of size 4 at ... thread T0
//   #0 ... in main+0x19c (.../sol-02-asan:arm64+0x1000009b4)
//   Address ... is located 0 bytes to the right of 32-byte region ...
// 修复：把第 22 行循环条件 i <= n 改为 i < n；重新编译后 ASan 不再报错。
// 注：常规环境（Linux CI 等）报告会带 file:line（如 main.cpp:25）；本机因验证
// 沙箱限制外部符号化器无法启动，函数名与偏移仍可定位到 main。
