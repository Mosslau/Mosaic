// 来源：05-struct-datastruct.md 第 6 章示例 7 —— 图（邻接表）BFS 最短跳数
// 设计要点：邻接表 = 指针数组 + 每顶点一条链表；BFS 第一次到达即最短跳数
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex07-graph-bfs.c -o ex07-graph-bfs
// 运行：./ex07-graph-bfs
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct AdjNode { int v; struct AdjNode *next; } AdjNode;

typedef struct {
    AdjNode **heads;    /* 每个顶点一条邻接链表 */
    int       n;        /* 顶点数 */
} Graph;

Graph *graph_create(int n) {
    Graph *g = malloc(sizeof(Graph));
    if (g == NULL) return NULL;
    g->n = n;
    g->heads = calloc((size_t)n, sizeof(AdjNode *));
    if (g->heads == NULL) { free(g); return NULL; }
    return g;
}

void graph_add_edge(Graph *g, int u, int v) {     /* 无向图：双向加边 */
    for (int a = u, b = v;;) {
        AdjNode *node = malloc(sizeof(AdjNode));
        if (node == NULL) return;
        node->v = b;
        node->next = g->heads[a];
        g->heads[a] = node;
        if (a == v) break;
        a = v; b = u;
    }
}

/* BFS：返回 src 到 dst 的最短跳数，不可达返回 -1 */
int graph_bfs(Graph *g, int src, int dst) {
    int *dist = malloc((size_t)g->n * sizeof(int));
    int *queue = malloc((size_t)g->n * sizeof(int));
    if (dist == NULL || queue == NULL) { free(dist); free(queue); return -1; }
    for (int i = 0; i < g->n; i++) dist[i] = -1;
    int head = 0, tail = 0;
    dist[src] = 0; queue[tail++] = src;
    while (head < tail) {
        int u = queue[head++];
        for (AdjNode *p = g->heads[u]; p != NULL; p = p->next)
            if (dist[p->v] == -1) {
                dist[p->v] = dist[u] + 1;
                queue[tail++] = p->v;
            }
    }
    int result = dist[dst];
    free(dist); free(queue);
    return result;
}

void graph_destroy(Graph *g) {
    for (int i = 0; i < g->n; i++) {
        AdjNode *cur = g->heads[i];
        while (cur != NULL) { AdjNode *tmp = cur; cur = cur->next; free(tmp); }
    }
    free(g->heads); free(g);
}

int main(void) {
    Graph *g = graph_create(6);
    if (g == NULL) return 1;
    graph_add_edge(g, 0, 1); graph_add_edge(g, 0, 2);
    graph_add_edge(g, 1, 3); graph_add_edge(g, 2, 4);
    graph_add_edge(g, 3, 5); graph_add_edge(g, 4, 5);
    printf("0 -> 5 最短跳数: %d\n", graph_bfs(g, 0, 5));   /* 3 */
    printf("1 -> 4 最短跳数: %d\n", graph_bfs(g, 1, 4));   /* 3 */
    graph_destroy(g);
    return 0;
}
