// sol-05-exception-safety.cpp —— 练习 5 参考实现：异常安全的资源类
// 练习 5 要求：实现 Buffer——(a) 构造函数获取两个资源，第二个失败时第一个不泄漏；
//   (b) assign() 提供强保证（copy-and-swap），失败时目标对象原封不动。
//   用计数器与"按需抛异常"的源对象实测两条性质。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 构造：第二个资源失败 → 第一个随成员析构，存活归零
//     ctor 主缓冲 64B（存活 1）
//     dtor 主缓冲 64B（存活 0）
//     捕获: 备用缓冲分配失败
//     构造失败后存活 = 0
//   [2] 构造：正常 → 两个资源，析构逆序释放
//     ctor 主缓冲 64B（存活 1）
//     ctor 备用缓冲 16B（存活 2）
//     dtor 备用缓冲 16B（存活 1）
//     dtor 主缓冲 64B（存活 0）
//   [3] assign 强保证：源拷贝抛异常 → 目标不变
//     ctor 主缓冲 64B（存活 1）      ← dst(false, 64)
//     ctor 备用缓冲 16B（存活 2）
//     ctor 主缓冲 16B（存活 3）      ← src(false, 16)
//     ctor 备用缓冲 16B（存活 4）
//     ctor 主缓冲 16B（存活 5）      ← 按值传参的拷贝开始…
//     dtor 主缓冲 16B（存活 4）      ← 拷贝中途抛 bad_alloc，半成品逆序析构
//     dtor 备用缓冲 16B（存活 3）
//     dtor 主缓冲 16B（存活 2）      ← src 随 catch 块结束析构
//     捕获 bad_alloc: dst.size=64（原封不动）
//   [4] assign 正常路径
//     ctor 主缓冲 16B（存活 3）      ← src2
//     ctor 备用缓冲 16B（存活 4）
//     ctor 主缓冲 16B（存活 5）      ← 按值传参拷贝成功
//     ctor 备用缓冲 16B（存活 6）
//     dtor 备用缓冲 16B（存活 5）    ← swap 后旧资源随临时对象析构
//     dtor 主缓冲 64B（存活 4）
//     assign 后 dst.size=16
//     最终存活 = 4（main 返回前还剩 dst/src2，main 结束后归零）
//     dtor 备用缓冲 16B（存活 3）
//     dtor 主缓冲 16B（存活 2）
//     dtor 备用缓冲 16B（存活 1）
//     dtor 主缓冲 16B（存活 0）
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-05-exception-safety.cpp -o /tmp/ph13-sol-05
// 运行：    /tmp/ph13-sol-05
// 验证状态：已验证（两种编译器均零警告；异常路径实测零泄漏、目标不变）
#include <cstdio>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>

// 计数资源：证明"有没有泄漏"
struct Res {
    static inline int alive = 0;
    std::string name;
    std::size_t size;
    Res(std::string n, std::size_t s) : name(std::move(n)), size(s) {
        ++alive;
        std::printf("  ctor %s %zuB（存活 %d）\n", name.c_str(), size, alive);
    }
    ~Res() {
        --alive;
        std::printf("  dtor %s %zuB（存活 %d）\n", name.c_str(), size, alive);
    }
    Res(const Res&) = delete;
    Res& operator=(const Res&) = delete;
};

class Buffer {
public:
    // (a) 构造：两个资源；第二个失败时，已构造成员 a_ 的析构自动释放第一个
    Buffer(bool fail_backup, std::size_t n = 64)
        : a_(std::make_unique<Res>("主缓冲", n)) {
        if (fail_backup) throw std::runtime_error("备用缓冲分配失败");
        b_ = std::make_unique<Res>("备用缓冲", 16);
    }

    // (b) assign：强保证 —— 先在临时对象上完成全部可能失败的操作，再 noexcept swap
    Buffer(const Buffer& o) {
        auto na = std::make_unique<Res>(o.a_->name, o.a_->size);   // 深拷贝
        if (copy_should_throw) throw std::bad_alloc();   // 模拟拷贝失败（练习用开关）
        a_ = std::move(na);
        if (o.b_ != nullptr) b_ = std::make_unique<Res>(o.b_->name, o.b_->size);
    }
    Buffer& operator=(Buffer o) noexcept {   // copy-and-swap：按值接收 + 交换
        swap(o);
        return *this;
    }
    Buffer(Buffer&&) noexcept = default;
    void swap(Buffer& o) noexcept {
        std::swap(a_, o.a_);
        std::swap(b_, o.b_);
    }

    std::size_t size() const { return a_->size; }

    static inline bool copy_should_throw = false;   // 练习演示开关
private:
    std::unique_ptr<Res> a_;
    std::unique_ptr<Res> b_;
};

int main() {
    std::printf("[1] 构造：第二个资源失败 → 第一个随成员析构，存活归零\n");
    try {
        Buffer bad(true);
    } catch (const std::runtime_error& e) {
        std::printf("  捕获: %s\n", e.what());
    }
    std::printf("  构造失败后存活 = %d\n", Res::alive);

    std::printf("[2] 构造：正常 → 两个资源，析构逆序释放\n");
    {
        Buffer ok(false);
    }
    std::printf("[3] assign 强保证：源拷贝抛异常 → 目标不变\n");
    Buffer dst(false, 64);
    Buffer::copy_should_throw = true;
    try {
        Buffer src(false, 16);
        dst = src;                // 拷贝构造临时对象时抛 bad_alloc → swap 未发生
    } catch (const std::bad_alloc&) {
        std::printf("  捕获 bad_alloc: dst.size=%zu（原封不动）\n", dst.size());
    }
    Buffer::copy_should_throw = false;

    std::printf("[4] assign 正常路径\n");
    Buffer src2(false, 16);
    dst = src2;
    std::printf("  assign 后 dst.size=%zu\n", dst.size());
    std::printf("  最终存活 = %d（main 返回前还剩 dst/src2，main 结束后归零）\n",
                Res::alive);
    return 0;
}
