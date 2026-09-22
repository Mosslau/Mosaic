// 来源：project/ —— RingBuffer 自测（assert 全过则输出一句话）
// 一句话说明：覆盖 FIFO 基本路径、满态拒绝、环形回绕、空态 pop、
//             front/back、满态首尾共 6 组断言。
// 验证环境：Apple clang 17（g++ 兼容），C++20
// 编译：g++ -Wall -Wextra -std=c++20 main.cpp -o ring_buffer
// 运行：./ring_buffer
// 验证状态：已验证
#include <cassert>
#include <iostream>
#include <optional>
#include <string>

#include "ring_buffer.h"

int main() {
    // 1. 基本 push/pop：FIFO 顺序
    RingBuffer<int, 4> rb;
    assert(rb.empty());
    assert(rb.size() == 0);
    assert(rb.capacity() == 4);
    rb.push(1); rb.push(2); rb.push(3);
    assert(rb.size() == 3);
    assert(rb.pop() == std::optional<int>(1));
    assert(rb.pop() == std::optional<int>(2));
    assert(rb.pop() == std::optional<int>(3));
    assert(rb.empty());

    // 2. 填满 + 满态拒绝 push + full 标记
    RingBuffer<int, 4> full;
    for (int i = 1; i <= 4; ++i) assert(full.push(i));
    assert(full.full());
    assert(full.size() == 4);
    assert(!full.push(5));            // 满时 push 返回 false，不覆盖旧数据

    // 3. 环形回绕：pop 两个后继续 push，读写指针越过数组尾部
    RingBuffer<int, 4> wrap;
    wrap.push(1); wrap.push(2); wrap.push(3); wrap.push(4);
    assert(wrap.pop() == std::optional<int>(1));
    assert(wrap.pop() == std::optional<int>(2));
    wrap.push(5); wrap.push(6);       // write_ 从 2 推进到 4，%4 回绕到 0
    assert(wrap.size() == 4);
    assert(wrap.pop() == std::optional<int>(3));
    assert(wrap.pop() == std::optional<int>(4));
    assert(wrap.pop() == std::optional<int>(5));
    assert(wrap.pop() == std::optional<int>(6));
    assert(wrap.empty());

    // 4. 空态 pop 返回 std::nullopt
    RingBuffer<int, 2> empty_buf;
    assert(!empty_buf.pop().has_value());

    // 5. front/back
    RingBuffer<std::string, 3> sb;
    sb.push("a");
    sb.push("b");
    assert(sb.front() == "a");
    assert(sb.back() == "b");
    sb.pop();
    assert(sb.front() == "b");

    // 6. 满态 front/back：write_ == read_ 时 back 取最后一次写入的槽
    RingBuffer<int, 3> fb;
    fb.push(10); fb.push(20); fb.push(30);
    assert(fb.full());
    assert(fb.front() == 10);
    assert(fb.back() == 30);

    std::cout << "Ring Buffer 全部 assert 通过\n";
    return 0;
}
