// ex06-exception-safety.cpp —— 异常安全资源释放：构造函数部分失败 + 基本/强保证
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex06-exception-safety.cpp -o /tmp/ph13-ex06
// 运行：/tmp/ph13-ex06
#include <cstdio>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>

// 计数资源：ctor/dtor 全局计数，用来证明"有没有泄漏"
struct Res {
    static inline int alive = 0;   // C++17 inline 变量：当前存活数
    std::string name;
    explicit Res(std::string n) : name(std::move(n)) {
        ++alive;
        std::printf("  Res ctor %s（存活 %d）\n", name.c_str(), alive);
    }
    ~Res() {
        --alive;
        std::printf("  Res dtor %s（存活 %d）\n", name.c_str(), alive);
    }
    Res(const Res&) = delete;
    Res& operator=(const Res&) = delete;
};

// 反例：裸指针成员 —— 构造第二个资源时抛异常，第一个资源泄漏
class TwoRaw {
public:
    TwoRaw(bool fail) : a_(new Res("A")), b_(nullptr) {
        if (fail) throw std::runtime_error("第二个资源获取失败");
        b_ = new Res("B");
    }
    ~TwoRaw() { delete a_; delete b_; }   // 构造抛异常时析构不会执行！
private:
    Res* a_;
    Res* b_;
};

// 正例：成员用 unique_ptr —— 构造中途抛异常，已构造成员逆序析构
class TwoSafe {
public:
    explicit TwoSafe(bool fail) : a_(std::make_unique<Res>("A")) {
        if (fail) throw std::runtime_error("第二个资源获取失败");
        b_ = std::make_unique<Res>("B");
    }
private:
    std::unique_ptr<Res> a_;
    std::unique_ptr<Res> b_;
};

// 可按需抛异常的字符串包装：模拟"拷贝中途失败"
struct Name {
    static inline bool throw_on_copy = false;
    std::string v;
    explicit Name(std::string s) : v(std::move(s)) {}
    Name(const Name& o) : v(o.v) {
        if (throw_on_copy) throw std::bad_alloc();   // 模拟拷贝资源耗尽
    }
    Name& operator=(const Name&) = default;
};

// 强保证：copy-and-swap —— 先在新对象上完成全部可能失败的操作，再 noexcept 交换
class Config {
public:
    explicit Config(std::string name) : name_(std::move(name)) {}
    Config(const Config&) = default;
    Config& operator=(Config o) noexcept {   // 按值接收：拷贝在此完成
        swap(o);                             // 交换本身不抛
        return *this;
    }
    void swap(Config& o) noexcept { std::swap(name_, o.name_); }
    const std::string& name() const { return name_.v; }
private:
    Name name_;
};

// 基本保证：赋值过程中抛异常，对象处于"合法但可能已改"的状态
class Fragile {
public:
    explicit Fragile(std::string a) : a_(std::move(a)) {}
    void assign(const Fragile& o) {
        a_.clear();              // 先破坏自身状态…
        a_ = o.a_;               // …若这里抛异常（bad_alloc），对象已变
    }
    const std::string& value() const { return a_; }
private:
    std::string a_;
};

int main() {
    std::printf("[1] 反例：裸指针 + 构造函数中途抛异常 → 泄漏（存活不归零）\n");
    {
        try { TwoRaw t(true); } catch (const std::runtime_error& e) {
            std::printf("  捕获: %s\n", e.what());
        }
        std::printf("  此时 Res 存活 = %d（应为 1：A 泄漏了）\n", Res::alive);
        Res::alive = 0;   // 仅为本演示清零计数；真实程序里这块内存已丢
    }

    std::printf("[2] 正例：unique_ptr 成员 + 构造函数中途抛异常 → 零泄漏\n");
    {
        try { TwoSafe t(true); } catch (const std::runtime_error& e) {
            std::printf("  捕获: %s\n", e.what());
        }
        std::printf("  此时 Res 存活 = %d（A 已随成员析构释放）\n", Res::alive);
    }

    std::printf("[3] 正常构造：两个资源都成功\n");
    {
        TwoSafe t(false);
    }
    std::printf("  此时 Res 存活 = %d\n", Res::alive);

    std::printf("[4] 强保证：copy-and-swap —— 拷贝失败时目标原封不动\n");
    Config dst("original");
    try {
        Name::throw_on_copy = true;          // 让来源的拷贝构造抛 bad_alloc
        Config src("updated");
        dst = src;                           // 拷贝在传参时抛异常 → swap 未发生
    } catch (const std::bad_alloc&) {
        std::printf("  捕获 bad_alloc: dst 仍是 %s（强保证成立）\n",
                    dst.name().c_str());
    }
    Name::throw_on_copy = false;
    Config src("updated");
    dst = src;                               // 正常路径：拷贝 + noexcept swap
    std::printf("  正常赋值成功: dst=%s\n", dst.name().c_str());
    std::printf("  要点：可能失败的操作都在 swap 之前完成；swap 标记 noexcept（E.16）\n");

    std::printf("[5] 基本保证对照：Fragile::assign 先清空再拷贝，中途失败对象已受损\n");
    Fragile f("data");
    f.assign(Fragile("new"));
    std::printf("  f.value=%s（正常路径无恙；异常路径只保证不泄漏、不保证原值）\n",
                f.value().c_str());
    return 0;
}
