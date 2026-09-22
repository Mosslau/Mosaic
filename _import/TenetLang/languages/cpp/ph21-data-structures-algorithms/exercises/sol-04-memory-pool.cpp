// sol-04-memory-pool.cpp —— 练习 4 参考实现：定长块内存池（free-list 结构）
// 对应主文档 3.1/3.11 与 roadmap §21 练习「内存池」。
// 教学点：内存池 = 预分配的连续块 + 空闲块链表/栈，alloc/free O(1) 且「先释放的后复用」
// （LIFO 让最近释放的块最先回到手里，cache 更热）；grow 模式按 chunk 扩容（多块 slab）。
// 本实现把「池结构」与「对象生命周期」分离：只管理字节块，块索引 = 结构身份；
// chunk 内存用 unique_ptr<char[]> 持有（R.11，无裸 new/delete），池自身 Rule of Zero。
// 边界：block_size=0 拒绝构造；越界索引 at() 抛 out_of_range；固定池耗尽 alloc 返回 nullopt。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra sol-04-memory-pool.cpp -o /tmp/ph21-sol04 && /tmp/ph21-sol04
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <cstddef>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

class fixed_block_pool {
public:
    // block_size：每块字节数；per_chunk：每 slab 的块数；grow=false 时池容量固定
    fixed_block_pool(std::size_t block_size, std::size_t per_chunk, bool grow)
        : block_size_{block_size}, per_{per_chunk}, grow_{grow} {
        if (block_size_ == 0 || per_ == 0) {
            throw std::invalid_argument("block size and blocks per chunk must be > 0");
        }
    }

    // 分配一块，返回块索引；grow=false 且池空时返回 nullopt（模拟有界池耗尽）
    std::optional<std::size_t> alloc() {
        if (free_.empty()) {
            if (!grow_ && !chunks_.empty()) {
                return std::nullopt;
            }
            add_chunk();
        }
        const std::size_t idx = free_.back();
        free_.pop_back();
        return idx;
    }

    void free_block(std::size_t idx) {
        if (idx >= capacity()) {
            throw std::out_of_range("free_block index out of range");
        }
        free_.push_back(idx);                 // 归还即入栈：先释放的后复用（LIFO）
    }

    // 非拥有观察指针：块借用期 = 分配到下一次 free_block 之间
    unsigned char* at(std::size_t idx) {
        if (idx >= capacity()) {
            throw std::out_of_range("at index out of range");
        }
        const std::size_t chunk = idx / per_;
        const std::size_t offset = (idx % per_) * block_size_;
        return reinterpret_cast<unsigned char*>(chunks_[chunk].get() + offset);
    }

    std::size_t block_size() const { return block_size_; }
    std::size_t capacity() const { return chunks_.size() * per_; }
    std::size_t free_count() const { return free_.size(); }
    std::size_t used_count() const { return capacity() - free_.size(); }

private:
    std::size_t block_size_;
    std::size_t per_;
    bool grow_;
    std::vector<std::unique_ptr<char[]>> chunks_;   // 每 chunk 一块连续内存
    std::vector<std::size_t> free_;                 // 空闲块索引栈

    void add_chunk() {
        const std::size_t chunk_id = chunks_.size();
        chunks_.push_back(std::make_unique<char[]>(per_ * block_size_));  // R.11：unique_ptr
        for (std::size_t i = 0; i < per_; ++i) {
            free_.push_back(chunk_id * per_ + i);   // 新 slab 的全部块入空闲栈
        }
    }
};

void demo_fixed_pool() {
    fixed_block_pool pool(8, 4, /*grow=*/false);    // 容量 4 块的有界池
    require(pool.block_size() == 8 && pool.capacity() == 0, "no chunk allocated yet");

    const auto b0 = pool.alloc();
    const auto b1 = pool.alloc();
    const auto b2 = pool.alloc();
    const auto b3 = pool.alloc();
    require(b0 && b1 && b2 && b3, "first 4 allocations succeed");
    require(pool.used_count() == 4, "all 4 blocks in use");
    require(pool.alloc() == std::nullopt, "fixed pool exhausted -> nullopt (bounded)");

    // 写到各自块里，验证块间不重叠（首字节可独立寻址）
    pool.at(*b0)[0] = 10;
    pool.at(*b1)[0] = 20;
    require(pool.at(*b0)[0] == 10 && pool.at(*b1)[0] == 20, "blocks do not overlap");

    // free 是 LIFO 复用：先放 b1 再放 b0，下一次分配应拿回 b0 的同一块索引
    pool.free_block(*b1);
    pool.free_block(*b0);
    require(pool.free_count() == 2, "two blocks freed");
    const auto again = pool.alloc();
    require(again && *again == *b0, "LIFO reuse: last freed block (b0) returned first");
    std::cout << "  fixed pool: bounded exhaustion + LIFO reuse passed\n";
}

void demo_growing_pool() {
    fixed_block_pool pool(4, 2, /*grow=*/true);     // 每 chunk 2 块、可增长
    const auto a0 = pool.alloc();
    const auto a1 = pool.alloc();
    const auto a2 = pool.alloc();                   // 越出第一 slab，触发 add_chunk
    require(a0 && a1 && a2, "growth mode never exhausts");
    require(pool.capacity() == 4, "second chunk added on demand (2 blocks per chunk)");
    require(pool.at(*a0) != pool.at(*a2), "blocks in different chunks are distinct memory");

    pool.free_block(*a1);
    const auto again = pool.alloc();
    require(again && *again == *a1, "cross-chunk free still LIFO-reused");
    std::cout << "  growing pool: chunked growth passed\n";
}

void demo_bad_inputs() {
    bool threw = false;
    try {
        fixed_block_pool bad(0, 4, false);
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    require(threw, "zero block size rejected");

    fixed_block_pool pool(8, 2, false);
    const auto b = pool.alloc();
    require(b.has_value(), "first alloc ok");
    threw = false;
    try {
        (void)pool.at(pool.capacity());             // 越界索引
    } catch (const std::out_of_range&) {
        threw = true;
    }
    require(threw, "out-of-range at() throws out_of_range");
    std::cout << "  bad inputs: invalid construction + out-of-range access passed\n";
}

}  // namespace

int main() {
    demo_fixed_pool();
    demo_growing_pool();
    demo_bad_inputs();
    std::cout << "sol-04-memory-pool OK\n";
    return 0;
}
