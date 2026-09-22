// exercises/sol-02-storage-modeling.cpp —— 练习 2 参考实现：Page/Block/Segment/VectorIndex 建模
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-storage-modeling.cpp -o sol02
// 运行：./sol02
// 已验证：本环境编译零警告，输出 13 / 1 / -1
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
    std::vector<Page> pages_;
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
    std::vector<Block> blocks_;
};

class VectorIndex {
public:
    void insert(int key) { keys_.push_back(key); }
    int find(int key) const {
        for (std::size_t i = 0; i < keys_.size(); ++i)
            if (keys_[i] == key) return static_cast<int>(i);
        return -1;
    }

private:
    std::vector<int> keys_;
};

int main() {
    Block b;
    b.add_page(Page{"row1"});
    b.add_page(Page{"row2-data"});
    Segment s;
    s.add_block(b);
    std::cout << s.total_size() << "\n";  // 4 + 9 = 13

    VectorIndex idx;
    idx.insert(10);
    idx.insert(20);
    idx.insert(30);
    std::cout << idx.find(20) << "\n";  // 1
    std::cout << idx.find(99) << "\n";  // -1
    return 0;
}
