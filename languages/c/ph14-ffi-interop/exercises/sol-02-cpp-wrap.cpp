// sol-02-cpp-wrap.cpp —— 参考实现: 用 C++ 包装 C 接口（RAII）
//
// 编译: c++ -Wall -Wextra -std=c++17 sol-02-cpp-wrap.cpp -o sol02
// 运行: ./sol02
// 验证环境: Apple clang 21.0.0（c++，macOS arm64）
// 验证状态: 已验证（零警告; total=42; g_live 进入=1、离开=0, 退出码 0;
//          实测输出见文件尾）
//
// 结构说明：
//   第一部分 = 给定的 C 接口（实际工程中这是 .h/.c，由 C 编译器编译；
//     为单文件自包含，这里用 C++ 实现——extern "C" 保证符号不 mangling，
//     链接语义与 C 编译完全一致）
//   第二部分 = 本题核心：C++ RAII 包装类，把 create/destroy 配对变成
//     构造/析构，杜绝忘记释放
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>

namespace {
int g_live = 0;   // 存活句柄计数：验证"谁 create 谁 destroy"
}

// ---------- 第一部分：C 接口（模拟给定 C 库） ----------
extern "C" {

struct counter;                        // opaque 句柄
counter *ctr_create(const char *label);
int32_t ctr_add(counter *c, int32_t v);
int64_t ctr_total(const counter *c);
int32_t ctr_destroy(counter *c);

}

// C 接口实现（C 调 C++ 包装层的形态：实现藏后面，只暴露 C 链接函数）。
// 注意：接口实现层允许 new/delete（它就是 C++ 侧的内存管理，等价于
// C 库里的 malloc/free）；真正的 C++ 业务代码（下面的包装类）遵守
// R.11，不裸持有资源。
struct counter {
    std::string label;
    std::int64_t total;
};

extern "C" counter *ctr_create(const char *label) {
    if (label == nullptr || label[0] == '\0')
        return nullptr;                // 失败返回 NULL（对应 C 惯例）
    counter *c = new counter{label, 0};
    ++g_live;
    return c;
}

extern "C" int32_t ctr_add(counter *c, int32_t v) {
    if (c == nullptr)
        return -1;                     // 错误码：0 成功, 负数错误
    c->total += v;
    return 0;
}

extern "C" int64_t ctr_total(const counter *c) {
    return c == nullptr ? 0 : c->total;
}

extern "C" int32_t ctr_destroy(counter *c) {
    if (c == nullptr)
        return -1;
    delete c;
    --g_live;
    return 0;
}

// ---------- 第二部分：C++ RAII 包装类（本题核心） ----------
class Counter {
public:
    explicit Counter(const char *label) {
        c_ = ctr_create(label);
        if (c_ == nullptr)
            throw std::runtime_error("ctr_create 失败（label 为空？）");
    }
    ~Counter() {
        if (c_ != nullptr)
            ctr_destroy(c_);           // RAII：离开作用域必释放
    }
    Counter(const Counter &) = delete;             // 句柄不可复制
    Counter &operator=(const Counter &) = delete;

    void add(std::int32_t v) {
        ctr_add(c_, v);
    }
    std::int64_t total() const {
        return ctr_total(c_);
    }

private:
    counter *c_;                       // 非拥有裸指针，由 RAII 类管理
};

int main() {
    std::printf("进入作用域前: g_live=%d\n", g_live);
    {
        Counter c("tally");            // 构造 → ctr_create
        c.add(40);
        c.add(2);
        std::printf("作用域内: total=%lld, g_live=%d\n",
                    static_cast<long long>(c.total()), g_live);
    }                                  // 离开作用域 → 析构 → ctr_destroy
    std::printf("离开作用域后: g_live=%d（RAII 保证释放）\n", g_live);
    return 0;
}

// 实测输出（本机一次运行）：
// 进入作用域前: g_live=0
// 作用域内: total=42, g_live=1
// 离开作用域后: g_live=0（RAII 保证释放）
