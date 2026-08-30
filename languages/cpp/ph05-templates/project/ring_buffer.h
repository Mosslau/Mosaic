// 来源：project/ —— 泛型 RingBuffer<T, N> 模板类头文件
// 一句话说明：非类型模板参数 N 在编译期定容量；requires 约束元素可默认构造且 N>0；
//             read/write 双指针环形取模，pop 用 std::optional 表达「空」结果。
// 模板类实现必须放头文件（实例化时需要完整定义），这是模板与普通类 .cpp/.h 分离的差异。
// 验证环境：Apple clang 17（g++ 兼容），C++20（requires 约束子句）
// 编译：g++ -Wall -Wextra -std=c++20 main.cpp -o ring_buffer
// 运行：./ring_buffer（头文件不单独编译，随 main.cpp 一起构建运行）
// 验证状态：已验证
#ifndef TENET_CPP_PH05_RING_BUFFER_H
#define TENET_CPP_PH05_RING_BUFFER_H

#include <array>
#include <concepts>
#include <cstddef>
#include <optional>
#include <utility>

template<typename T, std::size_t N>
  requires std::default_initializable<T> && (N > 0)
class RingBuffer {
public:
    bool push(const T& val) {
        if (full_) return false;
        buf_[write_] = val;
        advance_write();
        return true;
    }

    bool push(T&& val) {
        if (full_) return false;
        buf_[write_] = std::move(val);
        advance_write();
        return true;
    }

    // 空时返回 std::nullopt；非空时移出队首元素并推进读指针
    std::optional<T> pop() {
        if (empty()) return std::nullopt;
        T val = std::move(buf_[read_]);
        advance_read();
        return val;
    }

    // 前置条件：非空（front/back 不做检查）
    const T& front() const { return buf_[read_]; }
    T& front()             { return buf_[read_]; }

    // back 是最后一次写入的槽：write_ 前一个位置（取模）
    const T& back() const { return buf_[(write_ + N - 1) % N]; }
    T& back()             { return buf_[(write_ + N - 1) % N]; }

    bool empty() const { return !full_ && write_ == read_; }
    bool full()  const { return full_; }

    std::size_t size() const { return full_ ? N : (write_ + N - read_) % N; }
    static constexpr std::size_t capacity() { return N; }

private:
    void advance_write() {
        write_ = (write_ + 1) % N;
        full_ = write_ == read_;       // 写指针追上读指针 → 满
    }

    void advance_read() {
        full_ = false;                 // 读走一个必然不满
        read_ = (read_ + 1) % N;
    }

    std::array<T, N> buf_{};           // Rule of Zero：标准库成员管理生命周期
    std::size_t read_ = 0;             // 下一次 pop 的位置
    std::size_t write_ = 0;            // 下一次 push 的位置
    bool full_ = false;                // 区分「write_ == read_」时是空还是满
};

#endif  // TENET_CPP_PH05_RING_BUFFER_H
