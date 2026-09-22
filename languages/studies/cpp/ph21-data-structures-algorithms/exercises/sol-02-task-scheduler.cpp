// sol-02-task-scheduler.cpp —— 练习 2 参考实现：单核抢占式任务调度器（SRTF）
// 对应主文档 3.4/3.11 与 roadmap §21 练习「任务调度器」。
// 模型：任务 (id, release_time, burst)；单核、抢占式、最短剩余时间优先（SRTF）；
// 剩余时间相同按 id 小者优先（确定性 tie-break）。priority_queue 存 {剩余, id} 最小堆。
// 输出：每个任务的完成时间；断言一条已知输入的全部完成时间。
// 复杂度：O(总执行时长 × log n)；边界：无任务、任务之间有空闲期（跳时间）。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra sol-02-task-scheduler.cpp -o /tmp/ph21-sol02 && /tmp/ph21-sol02
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <functional>
#include <iostream>
#include <limits>
#include <queue>
#include <utility>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

struct task {
    int id;        // 唯一
    int release;   // 就绪时间（≥0）
    int burst;     // 需要执行的总时长（>0）
};

// 返回 finish[id]（完成后 >0；未轮到保持 0），并输出每个时间步正在执行的 id
std::vector<int> srtf_schedule(const std::vector<task>& tasks) {
    const std::size_t n = tasks.size();
    std::vector<int> finish(n, 0);
    std::vector<char> arrived(n, 0);
    // 最小堆：{剩余时长, id} —— 时长小的先跑，同长按 id 小先跑
    using item = std::pair<int, int>;
    std::priority_queue<item, std::vector<item>, std::greater<>> pq;

    std::size_t done = 0;
    int t = 0;
    while (done < n) {
        // 1. 就绪窗口：把所有 release <= t 的任务放进去
        for (std::size_t i = 0; i < n; ++i) {
            if (!arrived[i] && tasks[i].release <= t) {
                arrived[i] = 1;
                pq.push({tasks[i].burst, tasks[i].id});
            }
        }
        // 2. 没有可跑的：时间跳到下一个就绪点（处理任务之间的空闲期）
        if (pq.empty()) {
            int next_release = std::numeric_limits<int>::max();
            for (std::size_t i = 0; i < n; ++i) {
                if (!arrived[i]) {
                    next_release = std::min(next_release, tasks[i].release);
                }
            }
            require(next_release != std::numeric_limits<int>::max(),
                    "idle jump must find a future release while work remains");
            t = next_release;
            continue;
        }
        // 3. 挑剩余最短者执行 1 个时间片
        auto [remaining, id] = pq.top();
        pq.pop();
        ++t;
        if (remaining - 1 == 0) {
            finish[static_cast<std::size_t>(id)] = t;
            ++done;
        } else {
            pq.push({remaining - 1, id});                    // 未完成：压回去等下一次挑选
        }
    }
    return finish;
}

void demo_known_case() {
    // id0: release0 burst3；id1: release1 burst2；id2: release2 burst1；id3: release4 burst5
    const std::vector<task> tasks{{0, 0, 3}, {1, 1, 2}, {2, 2, 1}, {3, 4, 5}};
    const std::vector<int> finish = srtf_schedule(tasks);
    // 手推：t0-2 跑 A(id0)，t3 完成；随后 C(1片) t4 完成；B(2片) t5-6，t6 完成；D(5片) t7-11
    require(finish[0] == 3, "A(id0) finishes at t=3");
    require(finish[2] == 4, "C(id2, shortest remaining) preempts to finish at t=4");
    require(finish[1] == 6, "B(id1) finishes at t=6");
    require(finish[3] == 11, "D(id3) finishes at t=11");
    std::cout << "  known case: finish = {A:" << finish[0] << " B:" << finish[1]
              << " C:" << finish[2] << " D:" << finish[3] << "}\n";
}

void demo_boundaries() {
    const std::vector<task> none;                            // 空任务集：合法、直接结束
    require(srtf_schedule(none).empty(), "empty task set schedules nothing");

    // 带空闲期 + 同时就绪的退化用例：释放 0 的短任务应抢在长任务前完成
    const std::vector<task> gap{{0, 0, 4}, {1, 0, 1}, {2, 7, 1}};
    const std::vector<int> finish = srtf_schedule(gap);
    require(finish[1] == 1, "shortest job (id1) finishes first at t=1");
    require(finish[0] == 5, "long job (id0) runs after, finishes t=5");
    require(finish[2] == 8, "late job (id2) runs in idle gap, finishes t=8");
    std::cout << "  boundary: empty + idle-gap cases passed\n";
}

void demo_preemption() {
    // 真正的抢占：长任务 L(0,5) 跑着，t=3 到达短任务 S(1,1)，剩余更短 → 立即被抢
    const std::vector<task> tasks{{0, 0, 5}, {1, 3, 1}};
    const std::vector<int> finish = srtf_schedule(tasks);
    require(finish[1] == 4, "short task (id1) arrives at t=3 and preempts, finishes t=4");
    require(finish[0] == 6, "long task (id0) resumes and finishes t=6");
    std::cout << "  boundary: preemption case passed\n";
}

}  // namespace

int main() {
    demo_known_case();
    demo_boundaries();
    demo_preemption();
    std::cout << "sol-02-task-scheduler OK\n";
    return 0;
}
