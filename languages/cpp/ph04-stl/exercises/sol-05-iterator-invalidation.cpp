/* 故意出错示例：vector 扩容后继续使用失效迭代器 —— 必须用 -fsanitize=address 编译运行，否则勿运行 */
// 来源：exercises/README.md 练习 5 —— 迭代器失效实验参考实现
// 一句话说明：push_back 触发扩容时旧缓冲区被释放，之前保存的 begin() 迭代器悬垂，
//             解引用它是 use-after-free（未定义行为）；正确写法是先 reserve 预留容量。
// 验证环境：Apple clang 17.0.0（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -fsanitize=address -g sol-05-iterator-invalidation.cpp -o sol-05-iterator-invalidation
// 运行：./sol-05-iterator-invalidation    （预期：ASan 报 heap-use-after-free 后中止）
// 验证状态：普通编译（去掉 -fsanitize=address）零警告通过；ASan 二进制在本环境沙箱内
//           运行受限（无输出、进程挂起被终止），报错输出请读者本机验证。
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};   // capacity = 3
    auto it = v.begin();              // 指向 v[0]

    for (int i = 0; i < 10; ++i)
        v.push_back(i + 100);         // 多次扩容：旧缓冲区被 free，it 悬垂

    std::cout << "capacity now: " << v.capacity() << "\n";
    std::cout << "*it = " << *it << "\n";   // UB：读取已释放内存（use-after-free）
    return 0;
}
