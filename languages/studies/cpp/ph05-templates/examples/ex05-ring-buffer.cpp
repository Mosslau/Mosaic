// 来源：05-templates.md 第 6 章示例 5 —— RingBuffer<T, N>（推荐项目原型）
// 一句话说明：非类型模板参数 N 在编译期定容量，requires 约束元素可默认构造且 N>0；
//             read/write 双指针环形取模，pop 用 std::optional 表达「空」结果。
// 验证环境：Apple clang 17（g++ 兼容），C++20（涉及 requires 约束子句）
// 编译：g++ -Wall -Wextra -std=c++20 ex05-ring-buffer.cpp -o ex05-ring-buffer
// 运行：./ex05-ring-buffer
// 验证状态：已验证
#include <array>
#include <concepts>
#include <iostream>
#include <optional>
#include <utility>

template<typename T, std::size_t N>
  requires std::default_initializable<T> && (N > 0)
class RingBuffer {
public:
    bool push(const T& val) {
        if (full_) return false;
        buf_[write_] = val;
        write_ = (write_ + 1) % N;
        if (write_ == read_) full_ = true;
        return true;
    }

    std::optional<T> pop() {
        if (empty()) return std::nullopt;
        T val = std::move(buf_[read_]);
        read_ = (read_ + 1) % N;
        full_ = false;
        return val;
    }

    bool empty() const { return !full_ && write_ == read_; }
    bool full()  const { return full_; }
    std::size_t capacity() const { return N; }
    std::size_t size() const { return full_ ? N : (write_ + N - read_) % N; }

private:
    std::array<T, N> buf_{};
    std::size_t read_ = 0, write_ = 0;
    bool full_ = false;
};

int main() {
    RingBuffer<int, 4> rb;
    for (int i = 1; i <= 4; ++i) rb.push(i);
    std::cout << "cap=" << rb.capacity()
              << " full=" << std::boolalpha << rb.full()
              << " size=" << rb.size() << "\n";
    std::cout << "push(5) -> " << rb.push(5) << "\n";
    while (!rb.empty()) std::cout << *rb.pop() << " ";
    std::cout << "\nempty-pop has_value=" << rb.pop().has_value() << "\n";
    return 0;
}
