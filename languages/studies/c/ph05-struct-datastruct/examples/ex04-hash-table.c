// 来源：05-struct-datastruct.md 第 6 章示例 4 —— 哈希表（链地址法）词频统计
// 设计要点：哈希表存储动态分配 key，不依赖调用者字符串生命周期；销毁先 free(key) 再 free(node)
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex04-hash-table.c -o ex04-hash-table
// 运行：./ex04-hash-table
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HT_SIZE 101

typedef struct HTNode { char *key; int count; struct HTNode *next; } HTNode;
typedef struct { HTNode *buckets[HT_SIZE]; } HashTable;

static unsigned int ht_hash(const char *key) {
    unsigned int hash = 5381;
    int c;
    while ((c = *key++)) hash = ((hash << 5) + hash) + (unsigned int)c;
    return hash % HT_SIZE;
}

void ht_init(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++) ht->buckets[i] = NULL;
}

void ht_inc(HashTable *ht, const char *key) {
    unsigned int idx = ht_hash(key);
    for (HTNode *cur = ht->buckets[idx]; cur != NULL; cur = cur->next)
        if (strcmp(cur->key, key) == 0) { cur->count++; return; }
    HTNode *n = malloc(sizeof(HTNode));
    if (n == NULL) return;
    n->key = malloc(strlen(key) + 1);
    if (n->key == NULL) { free(n); return; }
    strcpy(n->key, key);
    n->count = 1;
    n->next = ht->buckets[idx];
    ht->buckets[idx] = n;
}

void ht_print(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++)
        for (HTNode *cur = ht->buckets[i]; cur != NULL; cur = cur->next)
            printf("  \"%s\": %d\n", cur->key, cur->count);
}

void ht_destroy(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++) {
        HTNode *cur = ht->buckets[i];
        while (cur != NULL) {
            HTNode *tmp = cur; cur = cur->next;
            free(tmp->key); free(tmp);
        }
        ht->buckets[i] = NULL;
    }
}

int main(void) {
    HashTable ht; ht_init(&ht);
    const char *words[] = {
        "hello","world","hello","c","world","hello",
        "data","c","struct","data","data", NULL};
    for (int i = 0; words[i] != NULL; i++) ht_inc(&ht, words[i]);
    printf("词频统计:\n"); ht_print(&ht);
    ht_destroy(&ht);
    return 0;
}
