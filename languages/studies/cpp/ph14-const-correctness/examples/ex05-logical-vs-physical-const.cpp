// ex05-logical-vs-physical-const.cpp —— 逻辑 const 与物理 const：位不变 ≠ 语义不变
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex05-logical-vs-physical-const.cpp -o /tmp/ph14-ex05
// 运行：/tmp/ph14-ex05
#include <cstdio>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

// 演示 1：物理 const —— const 对象的所有位冻结，编译器保证任何成员位不被写
struct Point {
    double x;
    double y;
};

// 演示 2：逻辑 const —— 懒计算缓存（mutable）：语义不变，物理位在变
class LazySize {
public:
    explicit LazySize(std::vector<int> data) : data_(std::move(data)) {}

    std::size_t size() const {
        if (!computed_) {
            std::printf("  size() 首次计算（物理位被写：computed_ 置位）\n");
            size_ = data_.size();
            computed_ = true;
        } else {
            std::printf("  size() 命中缓存（物理位未变，逻辑结果稳定）\n");
        }
        return size_;
    }

private:
    std::vector<int> data_;
    mutable bool computed_{false};      // 物理可变：缓存标志（不属于逻辑状态）
    mutable std::size_t size_{0};       // 物理可变：缓存值
};

// 演示 3：逻辑 const + 互斥锁 —— const 成员函数也要同步（mutable 锁，CP.20/CP.44）
class Stats {
public:
    void record(int v) {
        std::scoped_lock lk(mu_);
        sum_ += v;
        count_ += 1;
    }

    double average() const {
        std::scoped_lock lk(mu_);       // const 成员函数内加锁：锁是物理状态，须 mutable
        return count_ == 0 ? 0.0 : static_cast<double>(sum_) / count_;
    }

private:
    mutable std::mutex mu_;             // mutable：锁不影响逻辑语义（"线程安全"是实现的物理细节）
    int sum_{0};
    int count_{0};
};

// 演示 4：底层 const 只是"路径只读" —— const 指针看到的数据可能被别处改
void observe(const int* p, int* writer) {
    std::printf("  观察者（const int*）读到 %d\n", *p);
    *writer = 50;                        // 别处修改物理对象（不是通过 const 路径）
    std::printf("  别处修改后，观察者（const int*）再读 %d（路径只读，对象非冻结）\n", *p);
}

int main() {
    std::printf("[1] 物理 const：const 对象所有位冻结（Point p 的 x/y 不可写）\n");
    const Point p{1.0, 2.0};
    std::printf("  p = (%.1f, %.1f)（只读对象：p.x = 3 是编译错误）\n", p.x, p.y);

    std::printf("[2] 逻辑 const：mutable 缓存 —— 第一次算、第二次命中，语义不变\n");
    LazySize ls(std::vector<int>{1, 2, 3, 4});
    std::printf("  ls.size() = %zu\n", ls.size());
    std::printf("  ls.size() = %zu\n", ls.size());

    std::printf("[3] 逻辑 const：mutable 互斥锁 —— 并发读的 const 成员函数也要同步\n");
    Stats st;
    st.record(10);
    st.record(20);
    std::printf("  st.average() = %.1f（const 成员函数内 scoped_lock 保护共享位）\n",
                st.average());

    std::printf("[4] 对照：const 指针只约束「这条路径」，不冻结对象本身\n");
    int n = 7;
    observe(&n, &n);
    return 0;
}
