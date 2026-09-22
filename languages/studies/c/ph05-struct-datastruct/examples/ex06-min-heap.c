// 来源：05-struct-datastruct.md 第 6 章示例 6 —— 二叉堆（任务优先级队列）
// 设计要点：堆用数组存完全二叉树——父 i 的子 2i+1/2i+2；push 上浮、pop 下沉均 O(log n)
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex06-min-heap.c -o ex06-min-heap
// 运行：./ex06-min-heap
// 验证状态：已验证
#include <stdio.h>

#define HEAP_MAX 256

typedef struct { int data[HEAP_MAX]; int size; } MinHeap;

void heap_init(MinHeap *h) { h->size = 0; }

static void swap(int *a, int *b) { int t = *a; *a = *b; *b = t; }

int heap_push(MinHeap *h, int x) {
    if (h->size >= HEAP_MAX) return -1;
    int i = h->size++;
    h->data[i] = x;
    while (i > 0) {                         /* 上浮：比父小就换 */
        int parent = (i - 1) / 2;
        if (h->data[i] >= h->data[parent]) break;
        swap(&h->data[i], &h->data[parent]);
        i = parent;
    }
    return 0;
}

int heap_pop(MinHeap *h, int *out) {
    if (h->size == 0) return -1;
    *out = h->data[0];
    h->data[0] = h->data[--h->size];
    int i = 0;
    for (;;) {                              /* 下沉：与较小子比 */
        int l = 2 * i + 1, r = 2 * i + 2, smallest = i;
        if (l < h->size && h->data[l] < h->data[smallest]) smallest = l;
        if (r < h->size && h->data[r] < h->data[smallest]) smallest = r;
        if (smallest == i) break;
        swap(&h->data[i], &h->data[smallest]);
        i = smallest;
    }
    return 0;
}

int main(void) {
    MinHeap h; heap_init(&h);
    int tasks[] = {5, 1, 9, 3, 7};          /* 数字小 = 优先级高 */
    for (int i = 0; i < 5; i++) heap_push(&h, tasks[i]);

    printf("按优先级出队: ");
    int t;
    while (heap_pop(&h, &t) == 0) printf("%d ", t);   /* 1 3 5 7 9 */
    printf("\n");
    return 0;
}
