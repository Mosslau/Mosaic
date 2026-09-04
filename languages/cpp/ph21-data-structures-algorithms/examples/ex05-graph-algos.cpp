// ex05-graph-algos.cpp —— 图与邻接表：BFS 无权最短路 / DFS 可达性 / Dijkstra 带权最短路
// 对应主文档 3.5/3.12。教学点：邻接表 vector<vector<pair>> 是默认表示；BFS 用 queue 且
// visited 在入队时标记；Dijkstra 用最小堆 + 懒删除（过期条目 d != dist[u] 直接丢弃）；
// 距离用 long long 防溢出；孤立点返回 -1/INF 是显式边界。
// 复杂度：BFS/DFS O(V+E)；Dijkstra O((V+E) log V)。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++，默认）+ Homebrew clang 21.1.8 交叉核对
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex05-graph-algos.cpp -o /tmp/ph21-ex05 && /tmp/ph21-ex05
// 验证状态：已验证（双编译器零警告、断言全绿、退出码 0）
#include <cstdint>
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

struct graph {
    int n;                                                  // 顶点数，编号 0..n-1
    std::vector<std::vector<std::pair<int, int>>> adj;      // adj[u] = {(v, w), ...}

    explicit graph(int vertices)
        : n{vertices}, adj(static_cast<std::size_t>(vertices)) {}

    void add_edge(int u, int v, int w) {
        adj[static_cast<std::size_t>(u)].push_back({v, w});
        adj[static_cast<std::size_t>(v)].push_back({u, w});  // 无向图：双向
    }
};

// BFS：无权图最短路（dist[v] = 源到 v 的最小边数），孤立点保留 -1
std::vector<int> bfs_shortest(const graph& g, int src) {
    std::vector<int> dist(static_cast<std::size_t>(g.n), -1);
    std::queue<int> q;
    dist[static_cast<std::size_t>(src)] = 0;
    q.push(src);
    while (!q.empty()) {
        const int u = q.front();
        q.pop();
        for (const auto& [v, w] : g.adj[static_cast<std::size_t>(u)]) {
            (void)w;                                        // 无权 BFS 忽略边长
            if (dist[static_cast<std::size_t>(v)] == -1) {  // 首次到达即最短路
                dist[static_cast<std::size_t>(v)] = dist[static_cast<std::size_t>(u)] + 1;
                q.push(v);                                  // ★ 入队时标记，防重复入队
            }
        }
    }
    return dist;
}

// DFS：从 src 出发的可达集合（递归版，链式深图有栈溢出风险——工程里换显式栈）
void dfs_rec(const graph& g, int u, std::vector<char>& visited) {
    visited[static_cast<std::size_t>(u)] = 1;
    for (const auto& [v, w] : g.adj[static_cast<std::size_t>(u)]) {
        (void)w;
        if (!visited[static_cast<std::size_t>(v)]) {
            dfs_rec(g, v, visited);
        }
    }
}

std::vector<char> dfs_reachable(const graph& g, int src) {
    std::vector<char> visited(static_cast<std::size_t>(g.n), 0);
    dfs_rec(g, src, visited);
    return visited;
}

// Dijkstra：非负权最短路，priority_queue + 懒删除
std::vector<long long> dijkstra(const graph& g, int src) {
    constexpr long long k_inf = std::numeric_limits<long long>::max() / 4;
    std::vector<long long> dist(static_cast<std::size_t>(g.n), k_inf);
    using item = std::pair<long long, int>;                          // {距离, 节点}：距离在前
    std::priority_queue<item, std::vector<item>, std::greater<>> pq; // 最小堆
    dist[static_cast<std::size_t>(src)] = 0;
    pq.push({0, src});
    while (!pq.empty()) {
        const auto [d, u] = pq.top();
        pq.pop();
        if (d != dist[static_cast<std::size_t>(u)]) {
            continue;                                   // ★ 懒删除：过期条目直接丢
        }
        for (const auto& [v, w] : g.adj[static_cast<std::size_t>(u)]) {
            if (dist[static_cast<std::size_t>(u)] + w < dist[static_cast<std::size_t>(v)]) {
                dist[static_cast<std::size_t>(v)] = dist[static_cast<std::size_t>(u)] + w;
                pq.push({dist[static_cast<std::size_t>(v)], v});    // 改进就压新条目
            }
        }
    }
    return dist;
}

void demo_bfs() {
    graph g(6);                              // 无权图（全 1 权）
    g.add_edge(0, 1, 1);
    g.add_edge(0, 2, 1);
    g.add_edge(1, 3, 1);
    g.add_edge(2, 3, 1);
    g.add_edge(3, 4, 1);
    const std::vector<int> dist = bfs_shortest(g, 0);
    require(dist == std::vector<int>({0, 1, 1, 2, 3, -1}),
            "bfs distances (node 5 isolated -> -1)");
    std::cout << "  bfs: unit distances + isolated node boundary passed\n";
}

void demo_dfs() {
    graph g(5);
    g.add_edge(0, 1, 1);
    g.add_edge(0, 2, 1);
    g.add_edge(2, 3, 1);
    const std::vector<char> reached = dfs_reachable(g, 0);
    require(reached[0] && reached[1] && reached[2] && reached[3], "dfs reaches component");
    require(!reached[4], "node 4 unreachable from 0");
    std::cout << "  dfs: reachability passed\n";
}

void demo_dijkstra() {
    graph g(7);                              // 顶点 6 是孤立点
    g.add_edge(0, 1, 2);
    g.add_edge(0, 2, 5);
    g.add_edge(1, 2, 1);                     // 平行边：0→2 直连 5，绕 1 只要 3
    g.add_edge(1, 3, 7);
    g.add_edge(2, 3, 2);
    g.add_edge(3, 4, 3);
    g.add_edge(4, 5, 1);
    g.add_edge(2, 5, 8);
    g.add_edge(2, 2, 0);                     // 自环：严格 < 更新天然免疫

    const std::vector<long long> dist = dijkstra(g, 0);
    const long long inf = std::numeric_limits<long long>::max() / 4;
    require(dist[0] == 0, "source distance 0");
    require(dist[1] == 2, "direct edge 0-1 = 2");
    require(dist[2] == 3, "0->1->2 = 3 beats direct 5");
    require(dist[3] == 5, "0->1->2->3 = 3+2 = 5");
    require(dist[4] == 8, "dist 3 + 3 = 8");
    require(dist[5] == 9, "0..->4->5 = 8+1 = 9 beats 0->2->5 = 3+8");
    require(dist[6] == inf, "isolated vertex keeps INF");
    std::cout << "  dijkstra: weighted shortest paths + parallel/self-loop/isolated passed\n";
}

}  // namespace

int main() {
    demo_bfs();
    demo_dfs();
    demo_dijkstra();
    std::cout << "ex05-graph-algos OK\n";
    return 0;
}
