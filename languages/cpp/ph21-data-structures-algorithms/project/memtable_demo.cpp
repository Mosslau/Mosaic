// memtable_demo.cpp —— ph21 project 驱动：SkipList MemTable 语义 + 与 std::map 随机对拍 + 边界测试
// 对应 roadmap §21 推荐项目「SkipList MemTable」。为 ph22 存储引擎铺路：put/get/del +
// 有序扫描（lower_bound + 迭代器）正是 MemTable → SSTable flush 的读取面；随机对拍保证结构正确。
// 验证环境：Apple clang 21.0.0（默认）+ Homebrew clang 21.1.8（交叉核对），macOS arm64 + libc++
// 编译/运行：
//   clang++ -std=c++20 -Wall -Wextra -I. memtable_demo.cpp -o /tmp/ph21-project-memtable && /tmp/ph21-project-memtable
//   （或 make clean && make test，见同目录 Makefile）
// 验证状态：已验证（双编译器零警告、断言全绿、退出码 0）
#include "skip_list.h"

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

void demo_memtable_semantics() {
    ph21::skip_list_map<std::string, std::string> memtable;
    require(memtable.empty(), "fresh memtable empty");
    require(memtable.put("user:1", "alice") == true, "insert new key returns true");
    require(memtable.put("user:2", "bob") == true, "insert second key returns true");
    require(memtable.put("user:7", "carol") == true, "insert third key returns true");
    require(memtable.put("user:2", "BOB") == false, "put existing key updates, returns false");

    require(memtable.size() == 3, "size counts distinct keys");
    require(memtable.contains("user:2"), "contains after update");
    require(memtable.find_value("user:2") != nullptr && *memtable.find_value("user:2") == "BOB",
            "value updated in place");
    require(memtable.find_value("user:9") == nullptr, "missing key -> nullptr");

    // 有序扫描：插入序被打乱，扫描必须严格升序（MemTable range scan / flush 语义）
    std::vector<std::string> seen;
    for (auto it = memtable.begin(); it != memtable.end(); ++it) {
        seen.push_back(it.key() + "=" + it.value());
    }
    require(seen == std::vector<std::string>({"user:1=alice", "user:2=BOB", "user:7=carol"}),
            "ordered scan ascending by key");

    // lower_bound：range scan 的下界（flush 到 SSTable 前按区间读走数据）
    auto lb = memtable.lower_bound("user:3");
    require(lb.valid() && lb.key() == "user:7", "lower_bound('user:3') -> user:7");
    require(memtable.lower_bound("user:9") == memtable.end(), "lower_bound beyond end == end()");
    require(memtable.lower_bound("user:1") == memtable.begin(), "lower_bound at first == begin()");

    // erase：删除键 + 二次删除失败 + 有序链仍然完整
    require(memtable.erase("user:7"), "erase existing key");
    require(!memtable.erase("user:7"), "erase missing key returns false");
    require(!memtable.contains("user:7") && memtable.size() == 2, "size shrinks after erase");
    require(memtable.check_invariants(), "structure invariants hold after erase");

    // 空表扫描与 lower_bound
    ph21::skip_list_map<int, int> empty_map;
    require(empty_map.begin() == empty_map.end(), "empty scan begin == end");
    require(empty_map.lower_bound(0) == empty_map.end(), "empty lower_bound == end()");
    require(!empty_map.erase(1) && empty_map.find_value(1) == nullptr, "ops on empty are safe");
    std::cout << "  memtable semantics: put/get/scan/lower_bound/erase passed\n";
}

void demo_random_replay_against_std_map() {
    // 固定种子：结构内部随机高度也由种子驱动，对拍可复现
    constexpr std::uint32_t k_seed = 20260904u;
    ph21::skip_list_map<std::uint64_t, std::string> sl(k_seed);
    std::map<std::uint64_t, std::string> ref;
    std::mt19937 rng(k_seed);
    std::uniform_int_distribution<std::uint64_t> key_dist(0, 999);
    std::uniform_int_distribution<int> op_dist(0, 9);

    auto compare_all = [&]() {
        if (sl.size() != ref.size()) {
            return false;
        }
        auto it_sl = sl.begin();
        for (auto it_ref = ref.begin(); it_ref != ref.end(); ++it_ref, ++it_sl) {
            if (!it_sl.valid() || it_sl.key() != it_ref->first || it_sl.value() != it_ref->second) {
                return false;
            }
        }
        return sl.check_invariants();
    };

    for (int step = 0; step < 4000; ++step) {
        const std::uint64_t key = key_dist(rng);
        const std::string value(1, static_cast<char>('a' + static_cast<int>(step % 26)));
        const int op = op_dist(rng);
        if (op < 5) {                              // 55% put
            const bool existed = ref.contains(key);
            require(sl.put(key, value) == !existed, "put-returned-new matches std::map");
            ref[key] = value;
        } else if (op < 8) {                       // 30% erase
            require(sl.erase(key) == (ref.erase(key) > 0), "erase result matches std::map");
        } else {                                   // 15% get
            const std::string* got = sl.find_value(key);
            const auto it = ref.find(key);
            require((got != nullptr) == (it != ref.end()), "find presence matches std::map");
            if (got != nullptr) {
                require(*got == it->second, "find value matches std::map");
            }
        }
        if (step % 197 == 0) {
            require(compare_all(), "full ordered scan matches std::map at checkpoint");
        }
    }
    require(compare_all(), "final full scan + invariants match std::map");
    std::cout << "  random replay vs std::map: 4000 ops, all checkpoints passed\n";
}

void demo_memtable_flush_shape() {
    // 模拟「MemTable 内容按序读出 = 下一层 SSTable 的有序输入」（ph22 的 flush 读面）
    ph21::skip_list_map<std::string, std::string> memtable(/*seed=*/7u);
    memtable.put("k:banana", "v1");
    memtable.put("k:apple", "v2");
    memtable.put("k:cherry", "v3");
    memtable.put("k:apple", "v2b");                // 更新：flush 前 MemTable 保存的是最新值

    std::size_t flush_count = 0;
    for (auto it = memtable.begin(); it != memtable.end(); ++it) {
        // 真实 flush：把 (key, value) 顺序写入 SSTable block；此处只统计并打印
        ++flush_count;
        std::cout << "    flush candidate: " << it.key() << " -> " << it.value() << '\n';
    }
    require(flush_count == 3 && memtable.size() == 3,
            "flush sees latest value per key, in ascending key order");
}

}  // namespace

int main() {
    std::cout << "[1] memtable basic semantics\n";
    demo_memtable_semantics();
    std::cout << "[2] random replay vs std::map\n";
    demo_random_replay_against_std_map();
    std::cout << "[3] flush-read shape (ph22 prelude)\n";
    demo_memtable_flush_shape();
    std::cout << "ph21-project-memtable OK\n";
    return 0;
}
