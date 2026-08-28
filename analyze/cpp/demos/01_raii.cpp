// 01 · RAII 资源管理演示
// 编译运行：make && ./demos/01_raii

#include <cstdio>
#include <iostream>
#include <memory>
#include <mutex>

// 自定义 RAII 守卫：构造时打印"进入"，析构时打印"释放"
class ScopeGuard {
public:
    explicit ScopeGuard(const char* name) : name_(name) {
        std::cout << "进入 " << name_ << "（资源已获取）\n";
    }
    ~ScopeGuard() {
        std::cout << "离开 " << name_ << "（资源自动释放）\n";
    }

private:
    const char* name_;
};

std::mutex g_mutex;

void work(bool early_return) {
    ScopeGuard guard("work");
    std::lock_guard<std::mutex> lock(g_mutex);  // RAII 锁：析构自动 unlock

    if (early_return) {
        std::cout << "  提前 return……\n";
        return;  // guard 和 lock 的析构依然执行
    }
    std::cout << "  正常路径完成\n";
}  // 无论哪条路径，析构都执行

int main() {
    std::cout << "== RAII：任何路径都自动释放 ==\n";
    work(false);
    work(true);

    std::cout << "\n== unique_ptr：谁拥有谁负责 ==\n";
    std::unique_ptr<int> p(new int(42));  // 唯一所有权
    std::cout << "*p = " << *p << "\n";
    // p 离开 main 时自动 delete，无需手动 free

    std::cout << "\n== 结束 ==\n";
}
