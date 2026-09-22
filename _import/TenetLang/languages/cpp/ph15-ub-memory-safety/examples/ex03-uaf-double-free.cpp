// ex03-uaf-double-free.cpp —— use-after-free 与重复释放：裸 new/delete 的生命周期误用
// 主题：new/delete 手动管理时，“释放后仍持有指针”产生两类 UB——释放后读写（use-after-
//       free）与重复释放（double free）。C++ 的解药不是“更小心地 delete”，而是消灭裸
//       delete（R.11：避免显式 new/delete；RAII 与 unique_ptr 绑定释放到对象生命周期）。
// 运行前提（故意出错变体，勿裸跑）：
//   -DEX03_UAF          必须用 c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address 编译运行
//   -DEX03_DOUBLE_FREE  同上
// 默认（无 -D）编译零警告：打印安全释放三模式（delete 后置空 / RAII / unique_ptr），可任意运行。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex03-uaf-double-free.cpp -o /tmp/ph15-ex03
// 运行：    /tmp/ph15-ex03
// 验证状态：已验证（默认零警告；两个变体报告实测记录于本文件底部注释）
#include <cstdio>
#include <memory>

// 危险路径 A：delete 之后继续写（use-after-free）
void demo_uaf() {
    int* p = new int(42);
    std::printf("uaf: *p=%d（delete 前）\n", *p);
    delete p;                              // p 成为悬空指针（dangling）
    std::printf("uaf: delete 后写 *p=1 ...\n");
    *p = 1;                                // UB: use-after-free（写已归还堆管理器的内存）
    std::printf("uaf: *p=%d\n", *p);       // （到不了这行：ASan 中止）
}

// 危险路径 B：同一指针 delete 两次（double free）
void demo_double_free() {
    int* p = new int(42);
    std::printf("dbl: *p=%d\n", *p);
    delete p;                              // 第一次释放
    std::printf("dbl: 再次 delete p ...\n");
    delete p;                              // UB: double free（第二次释放同一地址）
    std::printf("dbl: 双重 delete 返回（到不了这行）\n");
}

int main() {
#if defined(EX03_UAF)
    demo_uaf();
#elif defined(EX03_DOUBLE_FREE)
    demo_double_free();
#else
    // —— 安全对照（默认）：三种“让释放不再出错”的写法 ——
    std::printf("[1] delete 后立即置空：delete nullptr 是合法的（多次 delete 空指针无害）\n");
    {
        int* p = new int(42);
        delete p;
        p = nullptr;                       // 置空后，任何“忘了已释放”的重复 delete 都无害
        delete p;                          // 合法：delete nullptr
        std::printf("    delete 空指针两次 —— 无 UB、无崩溃（但置空只防当前别名）\n");
    }
    std::printf("[2] 资源绑定对象生命周期：RAII 让“释放”不可能被遗忘或重复\n");
    {
        class RaiiInt {
        public:
            explicit RaiiInt(int v) : v_(new int(v)) {}
            ~RaiiInt() { delete v_; }      // 析构是唯一释放点：调用方无法“提前/重复”释放
            int get() const { return *v_; }
        private:
            int* v_;
        };
        RaiiInt x(7);
        std::printf("    RaiiInt x.get()=%d（x 出作用域自动释放一次）\n", x.get());
    }
    std::printf("[3] 现代写法：unique_ptr 表达独占所有权（R.11/R.20），无裸 new/delete\n");
    {
        auto p = std::make_unique<int>(42);
        std::printf("    unique_ptr: *p=%d，离开作用域自动释放\n", *p);
    }
    std::printf("[4] 本文件故意出错变体：-DEX03_UAF（delete 后写）/ -DEX03_DOUBLE_FREE（双删）\n");
    std::printf("    报告见文件底部注释 —— ASan 两种都报（heap-use-after-free / double-free）\n");
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0，-O0/-O1/-O2 -g 均触发，ASan+UBSan 组合构建同）：
//   [默认] 输出 [1]~[4]；-Wall -Wextra 零警告（Homebrew clang 21.1.8 同）
//   [-DEX03_UAF + ASan] 退出码 134：
//     ERROR: AddressSanitizer: heap-use-after-free on address 0x... at pc ...
//     WRITE of size 4 at ... thread T0
//   [-DEX03_DOUBLE_FREE + ASan] 退出码 134：
//     ERROR: AddressSanitizer: attempting double-free on 0x... in thread T0:
//   （“delete 后置空”对照：置空后再 delete 零报告 —— 验证方法：删掉置空行重编译即报）
