// project/test_stl_utils.cpp —— stl_utils 的单元测试（用 examples/ex01 的 mini 框架）
// 覆盖：正常路径（push/pop 顺序、split/join）、异常路径（空 front、零容量）、
// 边界（容量 1、覆盖最旧、空串/连续分隔符）。
//
// 验证环境：Apple clang 21.0.0 + Homebrew clang 21.1.8
// 构建/运行：见同目录 Makefile（make test）；单独编译：
//   c++ -std=c++20 -Wall -Wextra -I../examples test_stl_utils.cpp -o /tmp/ph16cpp-proj-test
#include <optional>
#include <string>
#include <vector>

#include "ex01-mini-test.h" // 复用 examples/ex01 的最小断言框架（-I../examples）
#include "stl_utils.h"

using stl_utils::join;
using stl_utils::ring_buffer;
using stl_utils::split;

namespace {

// pop 并断言值；value_or 保证「空」也走断言失败而非抛异常（bugprone-unchecked-optional-access）
void expect_pop(ring_buffer<int>& rb, int want) {
    const std::optional<int> v = rb.try_pop();
    MINI_EXPECT_TRUE(v.has_value());
    MINI_EXPECT_EQ(v.value_or(-1), want);
}

} // namespace

MINI_TEST(RingBuffer, FifoOrder) {
    ring_buffer<int> rb(3);
    rb.push(1);
    rb.push(2);
    rb.push(3);
    MINI_EXPECT_TRUE(rb.full());
    MINI_EXPECT_EQ(rb.size(), 3);
    expect_pop(rb, 1); // 先进先出
    expect_pop(rb, 2);
    MINI_EXPECT_EQ(rb.size(), 1);
}

MINI_TEST(RingBuffer, OverwriteOldestWhenFull) {
    ring_buffer<int> rb(2);
    rb.push(1);
    rb.push(2);
    rb.push(3); // 覆盖最旧的 1
    MINI_EXPECT_EQ(rb.front(), 2);
    expect_pop(rb, 2);
    expect_pop(rb, 3);
    MINI_EXPECT_TRUE(rb.empty());
}

MINI_TEST(RingBuffer, EmptyPopIsNullopt) {
    ring_buffer<int> rb(2);
    MINI_EXPECT_TRUE(!rb.try_pop().has_value()); // 空 pop → nullopt（非异常非哨兵）
}

MINI_TEST(RingBuffer, EmptyFrontThrows) {
    ring_buffer<int> rb(2);
    bool threw = false;
    try {
        (void)rb.front();
    } catch (const std::out_of_range&) {
        threw = true;
    }
    MINI_EXPECT_TRUE(threw);
}

MINI_TEST(RingBuffer, ZeroCapacityThrows) {
    bool threw = false;
    try {
        ring_buffer<int> rb(0);
        (void)rb;
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    MINI_EXPECT_TRUE(threw);
}

MINI_TEST(RingBuffer, CapacityOne) {
    ring_buffer<int> rb(1); // 最小容量的边界
    rb.push(42);
    MINI_EXPECT_TRUE(rb.full());
    rb.push(43); // 立即覆盖
    expect_pop(rb, 43);
    MINI_EXPECT_TRUE(rb.empty());
}

MINI_TEST(Split, NormalAndEmptyFields) {
    const auto parts = split("a,b,,c", ',');
    MINI_EXPECT_EQ(parts.size(), 4); // 连续逗号 → 空字段
    MINI_EXPECT_EQ(parts[0], "a");
    MINI_EXPECT_EQ(parts[2], "");
    MINI_EXPECT_EQ(parts[3], "c");
}

MINI_TEST(Split, TrailingDelimAndEmptyInput) {
    MINI_EXPECT_EQ(split("a,", ',').size(), 2); // 尾部空字段
    MINI_EXPECT_EQ(split("", ',').size(), 1);   // 空串 → 一个空字段
    MINI_EXPECT_EQ(split("nodelim", ',').size(), 1);
}

MINI_TEST(Join, NormalAndEdgeCases) {
    MINI_EXPECT_EQ(join({"a", "b", "c"}, ","), "a,b,c");
    MINI_EXPECT_EQ(join({"only"}, ","), "only");
    MINI_EXPECT_EQ(join({}, ","), ""); // 空序列 → 空串
}

MINI_TEST(SplitJoin, RoundTrip) {
    const std::string line = "x,y,z";
    MINI_EXPECT_EQ(join(split(line, ','), ","), line); // 往返不变性
}

int main() {
    return MINI_RUN_ALL_TESTS();
}
