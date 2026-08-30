// 来源：exercises/README.md 练习 1 —— 用 unique_ptr 管理对象
// 参考实现（题解分离：题目见 README.md）
// 对应 roadmap 练习"用 unique_ptr 管理对象"
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-unique-ptr.cpp -o sol-01
// 运行：./sol-01
// 验证状态：已验证
#include <iostream>
#include <memory>
#include <string>

struct Resource {
    explicit Resource(const std::string& tag) : tag_(tag) {
        std::cout << "Resource(" << tag_ << ") 构造\n";
    }
    ~Resource() { std::cout << "Resource(" << tag_ << ") 析构\n"; }
    const std::string& tag() const { return tag_; }
private:
    std::string tag_;
};

int main() {
    {   // 作用域 1：离开作用域自动析构，无需手写 delete
        auto r = std::make_unique<Resource>("scope1");
        std::cout << "使用中: " << r->tag() << "\n";
    }

    // 所有权转移：move 后 r 变为 null，r2 成为唯一所有者
    auto r = std::make_unique<Resource>("moved");
    auto r2 = std::move(r);
    std::cout << "r 为空: " << std::boolalpha << (r == nullptr)
              << "，r2 持有: " << r2->tag() << "\n";

    // 对比：裸 new/delete 写法需要手动释放，忘写就泄漏；
    // unique_ptr 把释放绑定到对象生命周期（RAII），默认删除器在析构时 delete。
    return 0;
}
