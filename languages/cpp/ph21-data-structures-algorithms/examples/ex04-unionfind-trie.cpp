// ex04-unionfind-trie.cpp —— 两个 STL 无等价物的手写结构：并查集 + Trie
// 对应主文档 3.6/3.7。教学点：并查集 = 两个 vector 装下的森林（路径压缩 + 按大小合并，
// 均摊 O(α(n))）；Trie = 指针树但所有权必须 RAII（子节点 unique_ptr，析构自动递归）。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex04-unionfind-trie.cpp -o /tmp/ph21-ex04 && /tmp/ph21-ex04
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <array>
#include <cstddef>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

// ---------- 并查集：parent 数组 + size 数组，无需任何堆分配 ----------
class union_find {
public:
    explicit union_find(int n)
        : parent_(static_cast<std::size_t>(n)), size_(static_cast<std::size_t>(n), 1) {
        for (int i = 0; i < n; ++i) {
            parent_[static_cast<std::size_t>(i)] = i;
        }
    }

    int find(int x) {                                   // 路径压缩（迭代两遍，防深递归）
        int root = x;
        while (parent_[static_cast<std::size_t>(root)] != root) {
            root = parent_[static_cast<std::size_t>(root)];
        }
        while (parent_[static_cast<std::size_t>(x)] != x) {  // 第二遍：沿途直接挂根
            const int next = parent_[static_cast<std::size_t>(x)];
            parent_[static_cast<std::size_t>(x)] = root;
            x = next;
        }
        return root;
    }

    void unite(int a, int b) {                          // 按 size 合并：小树挂大树
        int ra = find(a);
        int rb = find(b);
        if (ra == rb) {
            return;
        }
        auto ua = static_cast<std::size_t>(ra);
        auto ub = static_cast<std::size_t>(rb);
        if (size_[ua] < size_[ub]) {
            std::swap(ua, ub);
        }
        parent_[ub] = static_cast<int>(ua);
        size_[ua] += size_[ub];
    }

    bool connected(int a, int b) { return find(a) == find(b); }

private:
    std::vector<int> parent_;
    std::vector<int> size_;
};

void demo_union_find() {
    union_find uf(6);                    // 顶点 0..5
    uf.unite(0, 1);
    uf.unite(2, 3);
    uf.unite(4, 5);
    uf.unite(1, 4);                      // 联通 0-1-4-5 与 2-3 仍分离
    require(uf.connected(0, 5), "chain 0-1-4-5 connected");
    require(!uf.connected(0, 2), "component 2-3 still separate");
    uf.unite(0, 2);                      // 全联通
    require(uf.connected(2, 5), "after union all vertices connected");
    require(uf.find(5) == uf.find(0), "find idempotent / same root");
    std::cout << "  union-find: component checks passed\n";
}

// ---------- Trie：26 叉指针树，子节点 unique_ptr 持有（R.11 无裸 new/delete）----------
class trie {
public:
    trie() : root_{std::make_unique<node>()} {}

    void insert(std::string_view word) {
        node* cur = root_.get();
        for (const char ch : word) {
            const auto idx = static_cast<std::size_t>(ch - 'a');  // 教学约定：小写 a-z
            if (!cur->children[idx]) {
                cur->children[idx] = std::make_unique<node>();
            }
            cur = cur->children[idx].get();
        }
        cur->terminal = true;
    }

    bool search(std::string_view word) const {
        const node* cur = find_prefix(word);
        return cur != nullptr && cur->terminal;         // 精确匹配：路径存在且词尾标记
    }

    bool starts_with(std::string_view prefix) const {
        return find_prefix(prefix) != nullptr;          // 前缀查询：哈希表做不到
    }

private:
    struct node {
        std::array<std::unique_ptr<node>, 26> children{};
        bool terminal{false};
    };

    // 沿字符下行；中途缺子节点说明前缀不存在，返回 nullptr
    const node* find_prefix(std::string_view s) const {
        const node* cur = root_.get();
        for (const char ch : s) {
            const auto idx = static_cast<std::size_t>(ch - 'a');
            if (!cur->children[idx]) {
                return nullptr;
            }
            cur = cur->children[idx].get();
        }
        return cur;
    }

    std::unique_ptr<node> root_;
};

void demo_trie() {
    trie t;
    t.insert("apple");
    t.insert("app");                     // "app" 是词，也是 "apple" 的前缀
    t.insert("apply");
    t.insert("bat");
    t.insert("batch");

    require(t.search("apple"), "exact word apple found");
    require(t.search("app"), "inserted shorter word app is a terminal");
    require(t.search("apply"), "exact word apply found");
    require(!t.search("appl"), "'appl' is prefix-only, not a word");
    require(!t.search("xyz"), "absent word rejected");
    require(t.starts_with("app"), "prefix 'app' exists");
    require(t.starts_with("batc"), "prefix 'batc' exists (of batch)");
    require(!t.starts_with("ca"), "prefix 'ca' does not exist");
    require(!t.search("batchx"), "longer-than-any-word rejected");
    std::cout << "  trie: prefix & exact match checks passed\n";
}

}  // namespace

int main() {
    demo_union_find();
    demo_trie();
    std::cout << "ex04-unionfind-trie OK\n";
    return 0;
}
