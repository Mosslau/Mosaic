// 来源：05-struct-datastruct.md 第 6 章示例 3 —— 链表队列（任务调度）
// 参考实现复用自 examples/ex03-linked-queue.c（题解分离：题目见 README.md）
// 设计要点：head+tail 双指针是 O(1) 入队前提；dequeue 队列变空时同步置 tail=NULL
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex03-linked-queue.c -o ex03-linked-queue
// 运行：./ex03-linked-queue
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct QNode { int data; struct QNode *next; } QNode;

typedef struct { QNode *head, *tail; int size; } Queue;

void queue_init(Queue *q) { q->head = q->tail = NULL; q->size = 0; }

int queue_enqueue(Queue *q, int data) {
    QNode *n = malloc(sizeof(QNode));
    if (n == NULL) return -1;
    n->data = data; n->next = NULL;
    if (q->tail == NULL) q->head = q->tail = n;
    else { q->tail->next = n; q->tail = n; }
    q->size++;
    return 0;
}

int queue_dequeue(Queue *q, int *out) {
    if (q->head == NULL) return -1;
    QNode *tmp = q->head;
    *out = tmp->data;
    q->head = q->head->next;
    if (q->head == NULL) q->tail = NULL;
    free(tmp);
    q->size--;
    return 0;
}

void queue_destroy(Queue *q) {
    while (q->head != NULL) {
        QNode *tmp = q->head;
        q->head = q->head->next;
        free(tmp);
    }
    q->tail = NULL; q->size = 0;
}

int main(void) {
    Queue q; queue_init(&q);
    printf("入队: T0 T1 T2 T3 T4\n");
    for (int i = 0; i < 5; i++) queue_enqueue(&q, i);
    printf("出队: ");
    int task;
    while (queue_dequeue(&q, &task) == 0) printf("T%d ", task);
    printf("\n队列空: %s\n", q.head == NULL ? "是" : "否");
    queue_destroy(&q);
    return 0;
}
