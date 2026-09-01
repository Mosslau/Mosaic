// ex02-rule-of-five.cpp —— Rule of Five（C.21）：手写析构就必须把五个都写对
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex02-rule-of-five.cpp -o /tmp/ph13-ex02
// 运行：/tmp/ph13-ex02
// 对照实验（故意出错路径，演示"只写析构"的后果，必须配合 ASan）：
//   c++ -std=c++20 -Wall -Wextra -DPH13_SHALLOW -fsanitize=address -g \
//       ex02-rule-of-five.cpp -o /tmp/ph13-ex02-shallow
//   /tmp/ph13-ex02-shallow   # ASan 报 double-free（实测退出码 134，SIGABRT）
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <utility>

// 资源类：唯一被允许直接持有裸资源（malloc 的内存）的地方。
// 手写析构 ⇒ 按 C.21 把拷贝构造/拷贝赋值/移动构造/移动赋值五个全部定义。
class HeapBuffer {
public:
    explicit HeapBuffer(std::size_t n) : data_(alloc(n)), size_(n) {
        std::printf("  ctor    size=%zu data=%p\n", size_, static_cast<void*>(data_));
    }
    ~HeapBuffer() {
        std::printf("  dtor    size=%zu data=%p\n", size_, static_cast<void*>(data_));
        std::free(data_);
    }
    // 拷贝构造：深拷贝（新内存 + 内容复制）
    HeapBuffer(const HeapBuffer& o) : data_(alloc(o.size_)), size_(o.size_) {
        std::memcpy(data_, o.data_, size_);
        std::printf("  copy    size=%zu data=%p (from %p)\n", size_,
                    static_cast<void*>(data_), static_cast<void*>(o.data_));
    }
    // 拷贝赋值：先造新资源再换入（异常安全，见 ex06）
    HeapBuffer& operator=(const HeapBuffer& o) {
        if (this != &o) {
            int* fresh = alloc(o.size_);          // 先分配成功…
            std::memcpy(fresh, o.data_, o.size_);
            std::free(data_);                     // …才释放旧资源
            data_ = fresh;
            size_ = o.size_;
            std::printf("  copy=   size=%zu data=%p\n", size_, static_cast<void*>(data_));
        }
        return *this;
    }
    // 移动构造：窃取指针 + 源置空（noexcept，E.16）
    HeapBuffer(HeapBuffer&& o) noexcept
        : data_(std::exchange(o.data_, nullptr)), size_(o.size_) {
        o.size_ = 0;
        std::printf("  move    size=%zu data=%p (源已置空)\n", size_,
                    static_cast<void*>(data_));
    }
    // 移动赋值：先释放自己的资源，再窃取
    HeapBuffer& operator=(HeapBuffer&& o) noexcept {
        if (this != &o) {
            std::free(data_);
            data_ = std::exchange(o.data_, nullptr);
            size_ = o.size_;
            o.size_ = 0;
            std::printf("  move=   size=%zu data=%p (源已置空)\n", size_,
                        static_cast<void*>(data_));
        }
        return *this;
    }

    std::size_t size() const { return size_; }
    void fill(int v) { for (std::size_t i = 0; i < size_; ++i) data_[i] = v; }
    int first() const { return size_ > 0 ? data_[0] : -1; }

private:
    static int* alloc(std::size_t n) {
        int* p = static_cast<int*>(std::malloc(n * sizeof(int)));
        if (p == nullptr && n > 0) throw std::bad_alloc();
        return p;
    }
    int* data_;
    std::size_t size_;
};

#if defined(PH13_SHALLOW)
// 故意出错：Rule of One —— 只写析构、不写拷贝/移动。
// 拷贝变成"逐成员浅拷贝"：两个对象持有同一指针 → 作用域结束 double free。
class ShallowBuffer {
public:
    explicit ShallowBuffer(std::size_t n)
        : data_(static_cast<int*>(std::malloc(n * sizeof(int)))) {}
    ~ShallowBuffer() { std::free(data_); }   // 只写了这一个！
    // 编译器仍生成逐成员拷贝 → data_ 被复制成两份相同指针
private:
    int* data_;
};
#endif

int main() {
#if defined(PH13_SHALLOW)
    std::printf("[危险路径] ShallowBuffer 只写析构 → 拷贝后 double free\n");
    {
        ShallowBuffer x(4);
        ShallowBuffer y = x;   // 浅拷贝：x.data_ 与 y.data_ 指向同一块内存
        (void)y;
    }   // y、x 先后析构 → 同一块内存 free 两次 → ASan: double-free
    return 0;
#else
    std::printf("[1] 构造 + 拷贝构造（深拷贝，内存地址不同）\n");
    HeapBuffer a(4);
    a.fill(7);
    HeapBuffer b = a;                       // 深拷贝
    std::printf("  a.first=%d b.first=%d（各自独立内存）\n", a.first(), b.first());

    std::printf("[2] 拷贝赋值（先造新资源再释放旧的）\n");
    HeapBuffer c(2);
    c = a;

    std::printf("[3] 移动构造（窃取指针，源置空）\n");
    HeapBuffer d = std::move(b);
    std::printf("  b.size=%zu d.size=%zu d.first=%d\n", b.size(), d.size(), d.first());

    std::printf("[4] 移动赋值（释放自身 + 窃取）\n");
    HeapBuffer e(1);
    e = std::move(d);

    std::printf("[5] 作用域结束：e/c/a 逆序析构；被移空的 b/d 析构安全（free(nullptr)）\n");
    return 0;
#endif
}
