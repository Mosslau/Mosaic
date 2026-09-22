// 来源：05-struct-datastruct.md 第 6 章示例 1 —— 单链表（增删查改 + 完整生命周期）
// 参考实现复用自 examples/ex01-linked-list.c（题解分离：题目见 README.md）
// 设计要点：Node **head 二级指针修改头指针；list_destroy 最后置 NULL 防悬空
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex01-linked-list.c -o ex01-linked-list
// 运行：./ex01-linked-list
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int          data;
    struct Node *next;
} Node;

Node *node_create(int data) {
    Node *n = malloc(sizeof(Node));
    if (n == NULL) return NULL;
    n->data = data;
    n->next = NULL;
    return n;
}

void list_insert_head(Node **head, int data) {
    Node *n = node_create(data);
    if (n == NULL) return;
    n->next = *head;
    *head = n;
}

void list_insert_tail(Node **head, int data) {
    Node *n = node_create(data);
    if (n == NULL) return;
    if (*head == NULL) { *head = n; return; }
    Node *cur = *head;
    while (cur->next != NULL) cur = cur->next;
    cur->next = n;
}

int list_delete(Node **head, int data) {
    Node *cur = *head, *prev = NULL;
    while (cur != NULL && cur->data != data) {
        prev = cur; cur = cur->next;
    }
    if (cur == NULL) return 0;
    if (prev == NULL) *head = cur->next;   /* 删除头节点 */
    else              prev->next = cur->next;
    free(cur);
    return 1;
}

Node *list_find(Node *head, int data) {
    for (Node *cur = head; cur != NULL; cur = cur->next)
        if (cur->data == data) return cur;
    return NULL;
}

void list_print(Node *head) {
    for (Node *cur = head; cur != NULL; cur = cur->next)
        printf("%d%s", cur->data, cur->next ? " -> " : "");
    printf("\n");
}

void list_destroy(Node **head) {
    Node *cur = *head;
    while (cur != NULL) {
        Node *tmp = cur;
        cur = cur->next;
        free(tmp);
    }
    *head = NULL;
}

int main(void) {
    Node *head = NULL;
    list_insert_head(&head, 30); list_insert_head(&head, 20);
    list_insert_head(&head, 10);
    printf("头插 10,20,30: "); list_print(head);

    list_insert_tail(&head, 40);
    printf("尾插 40:       "); list_print(head);

    list_delete(&head, 20);
    printf("删除 20:       "); list_print(head);

    printf("查找 30:       %s\n", list_find(head, 30) ? "找到" : "未找到");

    list_destroy(&head);
    printf("销毁后: head=%p\n", (void *)head);
    return 0;
}
