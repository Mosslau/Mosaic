// examples/ex04-istorage-iexecutor.cpp —— IStorage/IExecutor 抽象接口：纯虚函数、override、虚析构
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex04-istorage-iexecutor.cpp -o ex04
// 运行：./ex04
// 已验证：本环境编译零警告，输出 read: page content / ScanExecutor running: table_scan users
#include <iostream>
#include <string>
#include <unordered_map>

class IStorage {
public:
    virtual ~IStorage() = default;  // C.35：多态基类必须有虚析构
    virtual void write(int page_id, const std::string& data) = 0;
    virtual std::string read(int page_id) = 0;
};

class MemoryStorage : public IStorage {
public:
    void write(int page_id, const std::string& data) override {  // C.128：重写标 override
        pages_[page_id] = data;
    }
    std::string read(int page_id) override {
        const auto it = pages_.find(page_id);
        return it == pages_.end() ? "" : it->second;
    }

private:
    std::unordered_map<int, std::string> pages_;
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

    ScanExecutor scanner;
    run_plan(scanner, "table_scan users");  // 基类引用 → 动态分派到派生类
    return 0;
}
