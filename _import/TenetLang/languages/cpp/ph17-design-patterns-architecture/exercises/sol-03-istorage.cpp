// exercises/sol-03-istorage.cpp —— 练习 3 参考实现：为存储引擎抽象 IStorage 接口
// 思路：IStorage 纯虚接口只声明契约（put/get/remove/size）；MemoryStorage（哈希直存）与
// JournaledStorage（只追加日志 + 回放读取）内部设计迥异却可互换；KVClient 只依赖接口，
// 同一组操作序列跑在两个实现上必须逐行一致（接口契约决定可替换性）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 exercises/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra sol-03-istorage.cpp -o /tmp/ph17cpp-sol03// 运行：/tmp/ph17cpp-sol03
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 预期输出：两个实现的逐行一致演示 + 断言行 + 全部通过，退出码 0
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace {

// ============ 抽象接口：存储契约（上层唯一依赖） ============
class IStorage {
public:
    virtual ~IStorage() = default;

    virtual void put(const std::string& key, const std::string& value) = 0;
    // 缺键返回 std::nullopt（用 optional 表达「可能没有」，而不是魔数/哨兵值）
    virtual std::optional<std::string> get(const std::string& key) const = 0;
    // remove 返回「是否真的删掉了」：删除不存在的键 → false（可诊断）
    virtual bool remove(const std::string& key) = 0;
    virtual std::size_t size() const = 0;
};

// ---- 实现 1：哈希直存（内存即真相） ----
class MemoryStorage final : public IStorage {
public:
    void put(const std::string& key, const std::string& value) override {
        data_[key] = value;  // 覆盖写
    }

    std::optional<std::string> get(const std::string& key) const override {
        const auto it = data_.find(key);
        if (it == data_.end()) {
            return std::nullopt;
        }
        return it->second;
    }

    bool remove(const std::string& key) override { return data_.erase(key) > 0; }

    std::size_t size() const override { return data_.size(); }

private:
    std::map<std::string, std::string> data_;
};

// ---- 实现 2：只追加日志（写操作只 append，读取时回放）----
// 与 MemoryStorage 完全不同的内部设计，但同一接口下可互换——接口的价值在此。
class JournaledStorage final : public IStorage {
public:
    void put(const std::string& key, const std::string& value) override {
        entries_.push_back(Entry{key, value, false});  // put 条目
    }

    std::optional<std::string> get(const std::string& key) const override {
        // 从最新条目往回找：命中删除墓碑 → 视为已删除；命中 put → 返回值
        for (auto it = entries_.rbegin(); it != entries_.rend(); ++it) {
            if (it->key == key) {
                if (it->is_delete) {
                    return std::nullopt;
                }
                return it->value;
            }
        }
        return std::nullopt;
    }

    bool remove(const std::string& key) override {
        if (!get(key)) {
            return false;  // 键本就不存在：不写墓碑
        }
        entries_.push_back(Entry{key, std::string{}, true});  // 删除墓碑
        return true;
    }

    std::size_t size() const override {
        // 回放压平出「存活键」集合
        std::map<std::string, std::string> alive;
        for (const Entry& e : entries_) {
            if (e.is_delete) {
                alive.erase(e.key);
            } else {
                alive[e.key] = e.value;
            }
        }
        return alive.size();
    }

private:
    struct Entry {
        std::string key;
        std::string value;
        bool is_delete;
    };
    std::vector<Entry> entries_;
};

// ============ 上层服务：只依赖接口（构造注入，非拥有引用） ============
class KVClient {
public:
    explicit KVClient(IStorage& storage) : storage_(storage) {}

    void set(const std::string& key, const std::string& value) {
        storage_.put(key, value);
    }

    std::optional<std::string> get(const std::string& key) const {
        return storage_.get(key);
    }

    bool remove(const std::string& key) { return storage_.remove(key); }

    std::size_t count() const { return storage_.size(); }

private:
    IStorage& storage_;  // 组合根保证 storage 活得比 KVClient 久
};

// ---- 自检小助手 ----
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

// 把同一组业务操作跑一遍，逐行记入 transcript（两个实现应产出相同 transcript）
void run_scenario(KVClient& client, std::vector<std::string>& transcript) {
    client.set("name", "alice");
    client.set("age", "30");
    transcript.push_back("get(name)  -> " + client.get("name").value_or("<missing>"));
    client.set("name", "alice2");  // 覆盖写
    transcript.push_back("get(name)  -> " + client.get("name").value_or("<missing>"));
    transcript.push_back("remove(age) -> " + std::to_string(client.remove("age")));
    transcript.push_back("get(age)  -> " + client.get("age").value_or("<missing>"));
    transcript.push_back("remove(age) again -> " + std::to_string(client.remove("age")));
    transcript.push_back("count()   -> " + std::to_string(client.count()));
}

}  // namespace

int main() {
    MemoryStorage mem;
    JournaledStorage journal;

    KVClient mem_client(mem);
    KVClient journal_client(journal);

    std::vector<std::string> transcript_mem;
    std::vector<std::string> transcript_journal;
    run_scenario(mem_client, transcript_mem);
    run_scenario(journal_client, transcript_journal);

    // ---- 两个实现的 observable 行为逐行一致 ----
    bool same = transcript_mem.size() == transcript_journal.size();
    if (same) {
        for (std::size_t i = 0; i < transcript_mem.size(); ++i) {
            if (transcript_mem[i] != transcript_journal[i]) {
                same = false;
                std::cout << "  不一致行 " << i << ": [" << transcript_mem[i] << "] vs ["
                          << transcript_journal[i] << "]\n";
                break;
            }
        }
    }
    check(same, "MemoryStorage 与 JournaledStorage 行为逐行一致（接口契约可替换）");

    for (const std::string& line : transcript_mem) {
        std::cout << "  " << line << '\n';
    }

    // ---- 具体语义断言（跑在 journal 实现上） ----
    check(journal_client.get("name").value_or("") == "alice2",
          "覆盖写取到新值");
    check(!journal_client.get("age").has_value(), "remove 后 get 返回空");
    check(journal_client.count() == 1, "size() = 存活键数");

    // ---- remove 不存在的键 ----
    check(!journal_client.remove("never-existed"), "删除不存在的键返回 false");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
