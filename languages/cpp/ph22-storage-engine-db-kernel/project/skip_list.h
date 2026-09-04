// 来源：本文件整体复制自同仓库 ph21-data-structures-algorithms/project/skip_list.h（ph21 阶段
// 综合项目核心组件），未做任何功能改动；验证状态与其 ph21 原文件一致（双编译器实测）。
// ph22 project（Mini LSM KV）按「直接复用 ph21 结构代码」原则以其作为内存 MemTable 的
// 底层有序结构——ph21 阶段写在「扩展方向」里的预告「接 WAL 的 replay 与 Compaction」在此兑现。
// 接口提醒（供 ph22 使用方）：namespace 为 ph21；有序扫描读面是 begin()/end()/lower_bound()；
// 值类型 V 需可默认构造、可拷贝/移动。
// skip_list.h —— 通用有序键值 Skip List（STL 无等价物的手写结构，ph21 project 核心）
// 对应主文档 3.x 三问表中的「SkipList：无 STL 等价物 → 手写」；roadmap §21 推荐项目「SkipList MemTable」。
// 教学点：① 概率平衡（p=1/2 逐层提升，期望 O(log n)），替代红黑树的旋转逻辑；
//           ② RAII：level-0 真链用 unique_ptr 持有（析构自动回收、erase 自动释放，无裸 new/delete，
//              R.11）；level>=1 的 skip 指针是 raw 非拥有快捷方式；
//           ③ 节点永不移动：find 返回的 const V* 在 erase 该键之前一直有效（与 std::map 同款保证）。
// 复杂度：put/get/erase/lower_bound 期望 O(log n)；空间 O(n)；
//         概率最坏（连续坏随机）O(n) —— p=1/2 + 16 层上限把退化压到可忽略。
// 接口：put（存在则更新值，返回 false）/erase（返回是否删除）/find_value/contains/lower_bound/
//       begin()/end() 有序扫描迭代器/size()/check_invariants()（测试用内部不变量校验）。
// 设计取舍：head 哨兵与普通节点同型；fwd[0] 恒等于 next.get()，保证「真链即 level-0」。
// 验证环境：Apple clang 21.0.0 + Homebrew clang 21.1.8，macOS arm64 + libc++
// 验证状态：已验证（双编译器零警告；对拍 std::map 的 4000 次随机操作 + 边界断言全绿，见 memtable_demo.cpp）
#ifndef PH21_PROJECT_SKIP_LIST_H
#define PH21_PROJECT_SKIP_LIST_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <random>
#include <vector>

namespace ph21 {

template <typename K, typename V, typename Compare = std::less<K>>
class skip_list_map {
    struct node;                       // 前向声明：iterator 先于完整定义使用指针

public:
    static constexpr int k_max_level = 16;
    static constexpr double k_p = 0.5;                 // 逐层提升概率

    explicit skip_list_map(std::uint32_t seed = 12345u)
        : rng_{seed}, dist_{0.0, 1.0} {
        head_ = std::make_unique<node>(k_max_level);
    }

    // 深拷贝代价高且非本阶段主题：禁用拷贝，允许移动（C.21：显式声明全部默认操作）
    skip_list_map(const skip_list_map&) = delete;
    skip_list_map& operator=(const skip_list_map&) = delete;
    skip_list_map(skip_list_map&&) = default;
    skip_list_map& operator=(skip_list_map&&) = default;
    ~skip_list_map() = default;                        // head_ 的 unique_ptr 链递归释放所有节点

    std::size_t size() const { return size_; }
    bool empty() const { return size_ == 0; }

    // 不存在则插入并返回 true；已存在则更新 value 并返回 false（memtable 的 put 语义）
    bool put(const K& key, V value) {
        std::array<node*, k_max_level> prev{};
        find_predecessors(key, prev);
        node* const target = prev[0]->fwd[0];
        if (target != nullptr && equal_key(target->key, key)) {
            target->value = std::move(value);          // 命中：更新值
            return false;
        }

        const int h = random_height();
        auto newnode = std::make_unique<node>(h);
        newnode->key = key;
        newnode->value = std::move(value);
        node* const raw = newnode.get();

        for (int l = 0; l < h; ++l) {                  // 新节点各层指向旧后继
            raw->fwd[static_cast<std::size_t>(l)] =
                prev[static_cast<std::size_t>(l)]->fwd[static_cast<std::size_t>(l)];
        }
        raw->next = std::move(prev[0]->next);          // level-0：接管原后继的整个真链
        prev[0]->next = std::move(newnode);            // prev[0] 变为新节点所有者
        prev[0]->fwd[0] = prev[0]->next.get();         // 保持 fwd[0] == next.get()
        raw->fwd[0] = raw->next.get();
        for (int l = 1; l < h; ++l) {                  // level>=1：前驱的 skip 指针指向新节点
            prev[static_cast<std::size_t>(l)]->fwd[static_cast<std::size_t>(l)] = raw;
        }
        ++size_;
        return true;
    }

    // 删除指定键；存在则删除并返回 true，否则 false。被删节点由 unique_ptr 自动析构
    bool erase(const K& key) {
        std::array<node*, k_max_level> prev{};
        find_predecessors(key, prev);
        node* const target = prev[0]->fwd[0];
        if (target == nullptr || !equal_key(target->key, key)) {
            return false;
        }
        for (int l = 0; l < target->height; ++l) {
            prev[static_cast<std::size_t>(l)]->fwd[static_cast<std::size_t>(l)] =
                target->fwd[static_cast<std::size_t>(l)];
        }
        prev[0]->next = std::move(target->next);       // 接管后继链，target 随之析构
        prev[0]->fwd[0] = prev[0]->next.get();
        --size_;
        return true;
    }

    // 非拥有只读指针：在 erase(key) 之前始终有效（节点不搬家，与 std::map 同款稳定性）
    const V* find_value(const K& key) const {
        const node* cur = head_.get();
        for (int l = k_max_level - 1; l >= 0; --l) {
            while (cur->fwd[static_cast<std::size_t>(l)] != nullptr &&
                   less_(cur->fwd[static_cast<std::size_t>(l)]->key, key)) {
                cur = cur->fwd[static_cast<std::size_t>(l)];
            }
        }
        const node* const found = cur->fwd[0];
        if (found == nullptr || !equal_key(found->key, key)) {
            return nullptr;
        }
        return &found->value;
    }

    bool contains(const K& key) const { return find_value(key) != nullptr; }

    // —— 有序扫描迭代器：range scan / flush 到 SSTable 的遍历入口 ——
    class const_iterator {
    public:
        const_iterator() = default;
        explicit const_iterator(const node* cur) : cur_{cur} {}

        const K& key() const { return cur_->key; }
        const V& value() const { return cur_->value; }
        bool valid() const { return cur_ != nullptr; }

        const_iterator& operator++() {
            cur_ = cur_->fwd[0];                       // level-0 真链前进
            return *this;
        }
        bool operator==(const const_iterator& other) const { return cur_ == other.cur_; }
        bool operator!=(const const_iterator& other) const { return cur_ != other.cur_; }

    private:
        const node* cur_{nullptr};
    };

    const_iterator begin() const { return const_iterator{head_->next.get()}; }
    const_iterator end() const { return const_iterator{nullptr}; }

    // 第一个 key >= 参数 的节点（range scan 的下界）；没有则等于 end()
    const_iterator lower_bound(const K& key) const {
        std::array<node*, k_max_level> prev{};
        find_predecessors(key, prev);
        return const_iterator{prev[0]->fwd[0]};
    }

    // —— 测试用：校验全部内部不变量（层间一致性 + 严格升序 + 计数）——
    bool check_invariants() const {
        const node* h = head_.get();
        if (h->fwd[0] != h->next.get()) {
            return false;
        }
        // level-0 真链：严格升序、fwd[0]==next、计数==size
        std::vector<const node*> seq;
        const node* prevnode = nullptr;
        for (const node* cur = h->next.get(); cur != nullptr; cur = cur->next.get()) {
            if (prevnode != nullptr && !less_(prevnode->key, cur->key)) {
                return false;
            }
            if (cur->height < 1 || cur->height > k_max_level || cur->fwd[0] != cur->next.get()) {
                return false;
            }
            seq.push_back(cur);
            prevnode = cur;
        }
        if (seq.size() != size_) {
            return false;
        }
        // level>=1：fwd[l] 链必须恰为「level-0 序列中 height>l 节点」的子序列
        for (int l = 1; l < k_max_level; ++l) {
            const node* p = h->fwd[static_cast<std::size_t>(l)];
            std::size_t i = 0;
            while (i < seq.size() && seq[i]->height <= l) {
                ++i;
            }
            while (p != nullptr) {
                if (i >= seq.size() || p != seq[i]) {
                    return false;
                }
                ++i;
                while (i < seq.size() && seq[i]->height <= l) {
                    ++i;
                }
                p = p->fwd[static_cast<std::size_t>(l)];
            }
            for (; i < seq.size(); ++i) {
                if (seq[i]->height > l) {
                    return false;
                }
            }
        }
        return true;
    }

private:
    struct node {
        explicit node(int level) : height{level} {}
        int height;                                    // 参与 0..height-1 层
        K key{};
        V value{};
        std::unique_ptr<node> next;                    // level-0 真链的所有权（RAII 根）
        std::array<node*, k_max_level> fwd{};          // skip 指针；fwd[0]==next.get()
    };

    Compare less_{};
    std::unique_ptr<node> head_;
    std::size_t size_{0};
    std::mt19937 rng_;
    std::uniform_real_distribution<double> dist_;

    // 找每个层的「最后一个 key < 参数」的前驱；返回后 prev[l] 都指向塔上的前驱
    void find_predecessors(const K& key, std::array<node*, k_max_level>& prev) const {
        node* cur = head_.get();
        for (int l = k_max_level - 1; l >= 0; --l) {
            while (cur->fwd[static_cast<std::size_t>(l)] != nullptr &&
                   less_(cur->fwd[static_cast<std::size_t>(l)]->key, key)) {
                cur = cur->fwd[static_cast<std::size_t>(l)];
            }
            prev[static_cast<std::size_t>(l)] = cur;
        }
    }

    bool equal_key(const K& a, const K& b) const {
        return !less_(a, b) && !less_(b, a);
    }

    int random_height() {
        int h = 1;
        while (h < k_max_level && dist_(rng_) < k_p) {
            ++h;
        }
        return h;
    }
};

}  // namespace ph21

#endif  // PH21_PROJECT_SKIP_LIST_H
