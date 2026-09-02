// project/stl_utils.h —— 带测试的 STL 工具库（ph16 project）：环形缓冲 + 字符串 split/join
// 设计取向（对应 cpp-coding-standards）：Rule of Zero（成员全是值/容器，C.20）、
// 查询函数 const（Con.2）、单参构造 explicit（C.46）、错误用异常（E.2）、
// 空 pop 用 std::optional 表达「可能无值」（比哨兵值更诚实）。
#ifndef PH16_STL_UTILS_H
#define PH16_STL_UTILS_H

#include <cstddef>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace stl_utils {

// 定容环形缓冲：写满后 push 覆盖最旧元素（日志缓冲语义）
template <typename T> class ring_buffer {
  public:
    explicit ring_buffer(std::size_t capacity) : buf_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument("ring_buffer capacity must be >= 1");
        }
    }

    void push(const T& value) {
        buf_[tail_] = value;
        tail_ = (tail_ + 1) % buf_.size();
        if (full_) { // 覆盖最旧：head 跟着前移
            head_ = tail_;
        } else if (tail_ == head_) { // 写满：tail 追上 head
            full_ = true;
        }
    }

    // 空时返回 nullopt——「可能无值」用类型表达，不用哨兵
    std::optional<T> try_pop() {
        if (empty()) {
            return std::nullopt;
        }
        T value = buf_[head_];
        head_ = (head_ + 1) % buf_.size();
        full_ = false;
        return value;
    }

    const T& front() const {
        if (empty()) {
            throw std::out_of_range("front() on empty ring_buffer");
        }
        return buf_[head_];
    }

    bool empty() const {
        return !full_ && head_ == tail_;
    }
    bool full() const {
        return full_;
    }
    std::size_t capacity() const {
        return buf_.size();
    }

    std::size_t size() const {
        if (full_) {
            return buf_.size();
        }
        return (tail_ + buf_.size() - head_) % buf_.size();
    }

  private:
    std::vector<T> buf_;
    std::size_t head_{0};
    std::size_t tail_{0};
    bool full_{false};
};

// 按单字符切分；连续分隔符产生空字段，结尾分隔符产生尾部空字段（与 std::getline 语义一致）
inline std::vector<std::string> split(std::string_view s, char delim) {
    std::vector<std::string> parts;
    std::size_t begin = 0;
    while (true) {
        const std::size_t pos = s.find(delim, begin);
        if (pos == std::string_view::npos) {
            parts.emplace_back(s.substr(begin));
            break;
        }
        parts.emplace_back(s.substr(begin, pos - begin));
        begin = pos + 1;
    }
    return parts;
}

// 用分隔符拼接；空序列返回空串
inline std::string join(const std::vector<std::string>& parts, std::string_view sep) {
    std::string out;
    for (std::size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) {
            out += sep;
        }
        out += parts[i];
    }
    return out;
}

} // namespace stl_utils

#endif // PH16_STL_UTILS_H
