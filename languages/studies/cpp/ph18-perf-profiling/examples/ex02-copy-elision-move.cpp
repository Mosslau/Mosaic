// examples/ex02-copy-elision-move.cpp —— 拷贝消除与移动语义教学完整版
// 教学点：返回局部对象不一定要拷贝——C++17 起 prvalue 的复制消除（copy elision）
// 是**语言保证**，不是优化开关；NRVO（具名返回值优化）是允许但非强制的消除。
// 本示例用带计数器的 Probe 把每次构造/拷贝/移动都数出来，先建立「拷贝 vs 移动
// 成本差两个量级」的直觉，再演示 vector 增长时 reserve 消灭重分配拷贝。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -O1 -Wall -Wextra ex02-copy-elision-move.cpp -o /tmp/ph18cpp-ex02
// 运行：/tmp/ph18cpp-ex02
// 预期输出：Probe 的构造/拷贝/移动计数 + vector 增长对比 + 断言行，退出码 0
// 验证状态：已验证（双编译器 -std=c++20 -Wall -Wextra 实测：编译零警告、运行通过）
//
// 说明：请在 -O1 及以上观察——复制消除需要优化器配合；-O0 下计数会「退步」，
// 那是编译器没开优化，不是语言语义变了。
#include <algorithm>
#include <cstddef>
#include <iostream>
#include <string>
#include <vector>

namespace {

int g_failures = 0;

void check(bool ok, const std::string& what) {
    std::cout << (ok ? "[通过] " : "[失败] ") << what << '\n';
    if (!ok) {
        ++g_failures;
    }
}

// 计数器探针：64 B 载荷模拟「复制成本高的对象」（如持堆缓冲的 std::string）。
// 数据成员禁拷贝并不影响 C++17 复制消除——消除意味着根本不调用拷贝/移动构造。
class Probe {
public:
    explicit Probe(int id) : id_(id) { ++ctor_count; }
    Probe(const Probe& other) : id_(other.id_) {
        std::copy_n(other.payload_, sizeof(payload_), payload_);  // 拷贝真搬 64 B
        ++copy_count;
    }
    Probe(Probe&& other) noexcept : id_(other.id_) { ++move_count; }  // 移动只搬 4 B 头
    Probe& operator=(const Probe&) = delete;  // 本示例只观察构造侧，赋值禁掉以聚焦
    Probe& operator=(Probe&&) = delete;

    int id() const { return id_; }

    static void reset_counts() {
        ctor_count = 0;
        copy_count = 0;
        move_count = 0;
    }
    static int copies() { return copy_count; }
    static int moves() { return move_count; }
    static std::size_t total() {
        return static_cast<std::size_t>(ctor_count + copy_count + move_count);
    }

private:
    int id_;
    unsigned char payload_[60]{};  // 64 B 对象：拷贝真的要搬 64 B，移动只是搬 4 B 头
    static int ctor_count;
    static int copy_count;
    static int move_count;
};

int Probe::ctor_count = 0;
int Probe::copy_count = 0;
int Probe::move_count = 0;

Probe make_direct(int id) { return Probe(id); }        // prvalue 返回：C++17 保证消除
Probe make_named(int id) {
    Probe local(id);                                    // 具名局部对象返回
    return local;                                       // NRVO：通常被消除（允许但非强制）
}
Probe make_conditional(bool pick_high) {
    Probe a(1);
    Probe b(2);
    if (pick_high) {
        return a;                                       // 条件返回两个具名对象之一
    }
    return b;                                           // 无法 NRVO → 必须移动（C++17 仍强制消除仅适用于 prvalue）
}

}  // namespace

int main() {
    // ---- 场景 1：按值返回的三种形态 ----
    Probe::reset_counts();
    const Probe p1 = make_direct(10);
    const int copies_direct = Probe::copies();
    const int moves_direct = Probe::moves();

    Probe::reset_counts();
    const Probe p2 = make_named(20);
    const int copies_nrvo = Probe::copies();
    const int moves_nrvo = Probe::moves();

    Probe::reset_counts();
    const Probe p3 = make_conditional(true);
    const int copies_cond = Probe::copies();
    const int moves_cond = Probe::moves();

    std::cout << "场景 1：按值返回（期望拷贝全部为 0）\n";
    std::cout << "  make_direct   prvalue 直接返回: 拷贝 " << copies_direct
              << "，移动 " << moves_direct << '\n';
    std::cout << "  make_named    NRVO 具名返回:    拷贝 " << copies_nrvo
              << "，移动 " << moves_nrvo << '\n';
    std::cout << "  make_conditional 条件返回:       拷贝 " << copies_cond
              << "，移动 " << moves_cond << "（无法 NRVO，退化为移动）\n\n";
    check(copies_direct == 0, "prvalue 返回零拷贝零移动（C++17 保证的复制消除）");
    check(copies_nrvo == 0, "NRVO 消除具名返回（优化器友好路径）");
    check(copies_cond == 0 && moves_cond == 1, "条件返回：消除不了，退化为一次移动而非拷贝");

    // ---- 场景 2：vector 增长——reserve 消灭重分配移动/拷贝 ----
    struct GrowthStats {
        std::size_t moves;
        std::size_t reallocs;
    };
    // 用容量日志记录重分配次数
    const auto growth = [](std::size_t reserve) {
        Probe::reset_counts();
        std::vector<Probe> v;
        if (reserve > 0) {
            v.reserve(reserve);  // 预分配：容量够就不重分配
        }
        std::size_t last_cap = v.capacity();
        std::size_t reallocs = 0;
        for (int i = 0; i < 257; ++i) {
            v.emplace_back(i);
            if (v.capacity() != last_cap) {
                last_cap = v.capacity();
                ++reallocs;
            }
        }
        return GrowthStats{static_cast<std::size_t>(Probe::moves()), reallocs};
    };

    const auto no_reserve = growth(0);
    const auto with_reserve = growth(257);

    std::cout << "场景 2：vector<Probe> 压入 257 个元素\n";
    std::cout << "  不 reserve: 重分配 " << no_reserve.reallocs << " 次，元素被移动 "
              << no_reserve.moves << " 次\n";
    std::cout << "  reserve(257): 重分配 " << with_reserve.reallocs << " 次，元素被移动 "
              << with_reserve.moves << " 次\n\n";
    check(no_reserve.reallocs > 0, "不 reserve 必然发生多次重分配");
    check(with_reserve.reallocs == 0 && with_reserve.moves == 0,
          "reserve 到位后零重分配零移动");

    // ---- 场景 3：push_back 临时对象走移动，push_back 具名对象走拷贝 ----
    Probe::reset_counts();
    {
        std::vector<Probe> v;
        v.reserve(4);
        v.push_back(Probe(30));                       // 临时对象 → 移动构造入容器
        Probe named(31);
        v.push_back(named);                           // 具名左值 → 拷贝构造入容器
    }
    std::cout << "场景 3：push_back 计数（拷贝应 1、移动应 1）\n";
    std::cout << "  拷贝 " << Probe::copies() << "，移动 " << Probe::moves() << "\n\n";
    check(Probe::copies() == 1 && Probe::moves() == 1,
          "push_back(临时)移动、push_back(左值)拷贝——代价差两个量级");

    const bool ok = (p1.id() == 10 && p2.id() == 20 && p3.id() == 1);
    check(ok, "三个返回值的内容正确");
    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
