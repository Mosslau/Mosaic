// sol-03-vector-invalidation.cpp —— 练习 3 参考实现：梳理 vector 迭代器/引用失效场景
// 练习 3 要求：梳理 std::vector 的迭代器/引用失效规则，写出“边遍历边修改”的安全姿势
//   （roadmap 练习 3「梳理 vector 迭代器失效场景」）。要点：重分配使全部引用/指针/迭代器
//   失效（std 标准保证）；erase/insert 使失效范围从修改点延伸到末尾；不重分配时，
//   修改点之前的引用仍有效——但为安全起见，惯例是“结构性修改后全部刷新”。
//
// 本机实测（本文件全部为安全写法；Apple clang 21.0.0 + Homebrew clang 21.1.8 零警告，
//   -fsanitize=address,undefined 复跑零报告）：输出见文件头底部注释。
//
// 失效速查（背下这张表，写循环前先过一遍）：
//   | 操作                | 引用/指针           | 迭代器            |
//   | push_back/insert/emplace/resize（触发重分配） | 全部失效 | 全部失效 |
//   | push_back 等（未重分配）   | 修改点之前有效，之后失效（插入点起） | 同左 |
//   | erase(it)           | it 起全部失效        | it 起全部失效（erase 返回下一迭代器）|
//   | clear()             | 全部失效            | 全部失效           |
//   | reserve(n)          | 全部失效（若重分配）  | 全部失效           |
//   | 只读操作（size/at/begin 不修改结构）          | 全部保持有效       | 全部保持有效 |
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-03-vector-invalidation.cpp -o /tmp/ph15-sol-03
// 运行：    /tmp/ph15-sol-03
// 验证状态：已验证（两种编译器零警告、输出一致；ASan+UBSan 复跑零报告）
#include <cstdio>
#include <vector>

// 把 vector 打印成 [1 2 3]（用常量引用遍历：只读不失效）
void print(const std::vector<int>& v) {
    std::printf("[");
    for (std::size_t i = 0; i < v.size(); ++i) {
        std::printf("%s%d", i == 0 ? "" : " ", v[i]);
    }
    std::printf("]");
}

int main() {
    std::printf("[1] 边遍历边删除（erase 循环）：用 erase 的返回值接住“下一个迭代器” ——\n");
    std::printf("    erase(it) 使 it 起全部失效，但返回值是新位置的下一个迭代器\n");
    {
        std::vector<int> v = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
        auto it = v.begin();
        while (it != v.end()) {
            if (*it % 2 == 0) {
                it = v.erase(it);          // 正确姿势：接收 erase 的返回值
            } else {
                ++it;
            }
        }
        std::printf("    删偶数后 v = ");
        print(v);
        std::printf("（erase 返回值 = 被删元素的下一个迭代器）\n");
    }

    std::printf("[2] 边遍历边插入（错误姿势是 ++it 跨过插入点）：先收集、后批量插入\n");
    {
        std::vector<int> v = {1, 2, 3, 4};
        std::vector<int> to_insert;        // 收集要在 3 前面插入的值
        for (int x : v) {
            if (x == 3) { to_insert.push_back(99); }
        }
        for (std::size_t i = 0; i < v.size(); ++i) {
            if (v[i] == 3) {
                v.insert(v.begin() + static_cast<std::ptrdiff_t>(i), to_insert.begin(),
                         to_insert.end());
                break;                     // 插入后所有迭代器失效：立即退出，重新取
            }
        }
        std::printf("    3 前插入 99 后 v = ");
        print(v);
        std::printf("（插入后迭代器全失效，改回下标/重新 begin）\n");
    }

    std::printf("[3] 扩容与 reserve：不预留容量时 push_back 到 cap 边界会重分配\n");
    {
        std::vector<int> v = {1, 2, 3};
        std::printf("    {1,2,3} 初始 size=%zu cap=%zu；", v.size(), v.capacity());
        v.push_back(4);
        std::printf("push_back 后 size=%zu cap=%zu（重分配发生，旧引用/迭代器失效）\n",
                    v.size(), v.capacity());
        std::vector<int> w;
        w.reserve(4);                      // 预留后写满前不重分配
        const int* p = w.data();
        for (int i = 0; i < 4; ++i) { w.push_back(i); }
        std::printf("    reserve(4) 后写满：cap=%zu，data() 指针仍有效（*p=%d）\n",
                    w.capacity(), *p);
    }

    std::printf("[4] 失效不是“崩溃预警”：用已失效迭代器是 UB，编译器不拦、不保证崩 ——\n");
    std::printf("    结构性修改后一律刷新（重新取下标 / begin() / erase 返回值）\n");
    return 0;
}
// 本机实测（两种编译器一致，零警告；+ASan+UBSan 零报告，退出码 0）：
//   [1] 删偶数后 v = [1 3 5 7 9]
//   [2] 3 前插入 99 后 v = [1 2 99 3 4]
//   [3] {1,2,3} 初始 size=3 cap=3；push_back 后 size=4 cap=6（重分配）
//       reserve(4) 后写满：cap=4，data() 指针仍有效（*p=0）
