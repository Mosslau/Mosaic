// exercises/sol-04-interfaces.cpp —— 练习 4 参考实现：IStorage/IIndex/IExecutor 接口与实现
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-interfaces.cpp -o sol04
// 运行：./sol04
// 已验证：本环境编译零警告，输出读回原文、contains 判断、ScanExecutor 执行信息
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

class IStorage {
public:
    virtual ~IStorage() = default;
    virtual void write(int page_id, const std::string& data) = 0;
    virtual std::string read(int page_id) = 0;
};

class MemoryStorage : public IStorage {
public:
    void write(int page_id, const std::string& data) override {
        pages_[page_id] = data;
    }
    std::string read(int page_id) override {
        const auto it = pages_.find(page_id);
        return it == pages_.end() ? "" : it->second;
    }

private:
    std::unordered_map<int, std::string> pages_;
};

class IIndex {
public:
    virtual ~IIndex() = default;
    virtual void insert(int key) = 0;
    virtual bool contains(int key) = 0;
};

class VectorIndex : public IIndex {
public:
    void insert(int key) override { keys_.push_back(key); }
    bool contains(int key) override {
        for (const int k : keys_)
            if (k == key) return true;
        return false;
    }

private:
    std::vector<int> keys_;
};

class IExecutor {
public:
    virtual ~IExecutor() = default;
    virtual void execute(const std::string& plan) = 0;
};

class ScanExecutor : public IExecutor {
public:
    void execute(const std::string& plan) override {
        std::cout << "ScanExecutor running: " << plan << "\n";
    }
};

void run_plan(IExecutor& exec, const std::string& plan) { exec.execute(plan); }

int main() {
    MemoryStorage storage;
    storage.write(1, "page content");
    std::cout << "read: " << storage.read(1) << "\n";

    VectorIndex index;
    index.insert(42);
    std::cout << "contains 42: " << index.contains(42) << "\n";
    std::cout << "contains 7: " << index.contains(7) << "\n";

    ScanExecutor scanner;
    run_plan(scanner, "table_scan users");
    return 0;
}
