// examples/ex02-page-block-segment.cpp —— Page/Block/Segment 建模：组合优于继承
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-page-block-segment.cpp -o ex02
// 运行：./ex02
// 已验证：本环境编译零警告，输出 segment total size: 13
#include <iostream>
#include <string>
#include <vector>

class Page {
public:
    explicit Page(const std::string& data) : data_(data) {}
    std::size_t size() const { return data_.size(); }

private:
    std::string data_;
};

class Block {
public:
    void add_page(const Page& page) { pages_.push_back(page); }
    std::size_t total_size() const {
        std::size_t sum = 0;
        for (const auto& p : pages_) sum += p.size();
        return sum;
    }

private:
    std::vector<Page> pages_;  // 组合：Block 持有多个 Page
};

class Segment {
public:
    void add_block(const Block& block) { blocks_.push_back(block); }
    std::size_t total_size() const {
        std::size_t sum = 0;
        for (const auto& b : blocks_) sum += b.total_size();
        return sum;
    }

private:
    std::vector<Block> blocks_;  // 组合：Segment 持有多个 Block
};

int main() {
    const Page p1{"row1"}, p2{"row2-data"};
    Block b;
    b.add_page(p1);
    b.add_page(p2);

    Segment s;
    s.add_block(b);
    std::cout << "segment total size: " << s.total_size() << "\n";
    return 0;
}
