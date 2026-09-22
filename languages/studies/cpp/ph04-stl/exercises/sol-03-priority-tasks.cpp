// 来源：exercises/README.md 练习 3 —— 优先级任务调度参考实现
// 一句话说明：priority_queue 小顶堆调度，operator< 双键比较——
//             priority 小的先执行，同 priority 按入队序号 seq 严格 FIFO。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-03-priority-tasks.cpp -o sol-03-priority-tasks
// 运行：./sol-03-priority-tasks
// 验证状态：已验证
#include <iostream>
#include <queue>
#include <string>
#include <vector>

struct Job {
    int priority;     // 数字越小优先级越高
    int seq;          // 入队序号：同优先级下先入队者先执行
    std::string name;

    // priority_queue 默认大顶堆（std::less），把「优先级更高」定义为「更小」即可反转为小顶堆
    bool operator<(const Job& other) const {
        if (priority != other.priority) return priority > other.priority;
        return seq > other.seq;  // 同优先级：seq 小的（先入队）先执行
    }
};

int main() {
    std::vector<Job> jobs = {
        {3, 0, "log-sync"},
        {1, 1, "heartbeat"},
        {2, 2, "gc-trigger"},
        {1, 3, "metrics-report"},
        {0, 4, "emergency"},
        {1, 5, "cache-warm"},
    };
    std::priority_queue<Job> pq;
    for (const auto& j : jobs) pq.push(j);

    std::cout << "=== execution order ===\n";
    while (!pq.empty()) {
        const Job& j = pq.top();
        std::cout << "[prio " << j.priority << ", seq " << j.seq << "] " << j.name << "\n";
        pq.pop();
    }
    return 0;
}
