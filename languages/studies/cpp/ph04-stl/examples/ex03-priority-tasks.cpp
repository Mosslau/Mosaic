// 来源：04-stl.md 第 6 章示例 3 —— 优先级任务调度（priority_queue + 自定义比较）
// 一句话说明：用 std::priority_queue 按优先级处理任务，operator< 反向实现小顶堆，
//             数字越小的优先级越高、先被弹出。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-priority-tasks.cpp -o ex03-priority-tasks
// 运行：./ex03-priority-tasks
// 验证状态：已验证
#include <iostream>
#include <queue>
#include <string>
#include <vector>

struct Task {
    int priority;     // 数字越小优先级越高
    std::string name;
    // 小顶堆：priority 小的在堆顶
    bool operator<(const Task& other) const {
        return priority > other.priority; // 故意反向：min-heap
    }
};

int main() {
    std::vector<Task> tasks = {
        {3, "log-sync"}, {1, "heartbeat"}, {2, "gc-trigger"}, {0, "emergency"}
    };
    std::priority_queue<Task> pq;
    for (const auto& t : tasks) pq.push(t);

    std::cout << "=== processing by priority ===\n";
    while (!pq.empty()) {
        const auto& t = pq.top();
        std::cout << "[" << t.priority << "] " << t.name << "\n";
        pq.pop();
    }
    return 0;
}
