// 来源：06-modern-cpp.md 第 6 章示例 1 —— 智能指针管理资源（make_unique / make_shared，RAII 替代裸 new/delete）
// 一句话说明：unique_ptr 唯一所有权 + move 转移、shared_ptr 共享所有权 + 引用计数、
//             weak_ptr 观察不持有；对象离开作用域自动释放，全程无手写 delete。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex01-smart-ptr.cpp -o ex01-smart-ptr
// 运行：./ex01-smart-ptr
// 验证状态：已验证
#include <iostream>
#include <memory>
#include <string>

struct FileHandle {                          // RAII：构造打开、析构关闭
    explicit FileHandle(const std::string& name) : name_(name) {
        std::cout << "open " << name_ << "\n";
    }
    ~FileHandle() { std::cout << "close " << name_ << "\n"; }
    const std::string& name() const { return name_; }
private:
    std::string name_;
};

int main() {
    auto f1 = std::make_unique<FileHandle>("data.db");     // 唯一所有权
    std::cout << "working on " << f1->name() << "\n";
    auto f2 = std::move(f1);                               // 所有权转移
    std::cout << "f1 is " << (f1 ? "alive" : "null") << " after move\n";

    auto shared = std::make_shared<FileHandle>("log.txt"); // 共享所有权
    std::shared_ptr<FileHandle> alias = shared;            // 计数 2
    std::cout << "use_count=" << shared.use_count() << "\n";

    std::weak_ptr<FileHandle> watcher = shared;            // 观察者，不增加计数
    if (auto sp = watcher.lock())
        std::cout << "watcher sees " << sp->name() << "\n";
    shared.reset();
    alias.reset();
    std::cout << "expired=" << watcher.expired() << "\n";
    return 0;
}
