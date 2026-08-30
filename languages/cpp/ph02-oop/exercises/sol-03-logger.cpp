// exercises/sol-03-logger.cpp —— 练习 3 参考实现：带 static 计数器的 Logger
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-03-logger.cpp -o sol03
// 运行：./sol03
// 已验证：本环境编译零警告，输出 4 条日志 + total logs: 4
#include <iostream>
#include <string>

class Logger {
public:
    explicit Logger(const std::string& module) : module_(module) {}

    void info(const std::string& msg) const {
        std::cout << "[INFO] [" << module_ << "] " << msg << "\n";
        ++log_count_;  // static 成员与对象无关，const 函数中可修改
    }
    static int log_count() { return log_count_; }

private:
    std::string module_;
    static int log_count_;
};

int Logger::log_count_ = 0;

int main() {
    const Logger db{"storage"}, net{"network"};
    db.info("page flushed");
    db.info("checkpoint done");
    net.info("connection opened");
    net.info("connection closed");
    std::cout << "total logs: " << Logger::log_count() << "\n";  // 4
    return 0;
}
