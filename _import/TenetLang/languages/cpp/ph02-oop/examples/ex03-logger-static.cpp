// examples/ex03-logger-static.cpp —— Logger：static 成员属于类而非对象
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-logger-static.cpp -o ex03
// 运行：./ex03
// 已验证：本环境编译零警告，输出两条日志 + total logs: 2
#include <iostream>
#include <string>

class Logger {
public:
    explicit Logger(const std::string& module) : module_(module) {}

    void info(const std::string& msg) const {
        std::cout << "[INFO] [" << module_ << "] " << msg << "\n";
        ++log_count_;  // static 成员不属于对象，const 函数中也可修改
    }
    static int log_count() { return log_count_; }  // static 成员函数无 this

private:
    std::string module_;
    static int log_count_;  // 声明
};

int Logger::log_count_ = 0;  // 定义与初始化（C++17 起可用 inline static 合并）

int main() {
    Logger db{"storage"}, net{"network"};
    db.info("page flushed");
    net.info("connection opened");
    std::cout << "total logs: " << Logger::log_count() << "\n";
    return 0;
}
