// 来源：exercises/README.md 练习 3 —— 64 字节固定块内存池参考实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 sol-03-mem-pool.c -o sol-03-mem-pool
// 运行：./sol-03-mem-pool
// 验证状态：已验证
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

#define POOL_BLOCK_SIZE 64
#define POOL_BLOCK_COUNT 16

typedef struct Block {
    struct Block *next;
    char          data[POOL_BLOCK_SIZE];
} Block;

typedef struct {
    Block *free_list;
    Block *chunk;
} MemPool;

int pool_init(MemPool *pool) {
    pool->chunk = malloc(POOL_BLOCK_COUNT * sizeof(Block));
    if (pool->chunk == NULL) return -1;
    pool->free_list = pool->chunk;
    for (int i = 0; i < POOL_BLOCK_COUNT - 1; i++)
        pool->chunk[i].next = &pool->chunk[i + 1];
    pool->chunk[POOL_BLOCK_COUNT - 1].next = NULL;
    return 0;
}

void pool_destroy(MemPool *pool) {
    free(pool->chunk);
    pool->chunk     = NULL;
    pool->free_list = NULL;
}

void *pool_alloc(MemPool *pool) {
    if (pool->free_list == NULL) return NULL;   /* 池满 */
    Block *blk = pool->free_list;
    pool->free_list = blk->next;
    return blk->data;
}

void pool_free(MemPool *pool, void *ptr) {
    if (ptr == NULL) return;
    Block *blk = (Block *)((char *)ptr - offsetof(Block, data));
    blk->next = pool->free_list;
    pool->free_list = blk;
}

int main(void) {
    MemPool pool;
    if (pool_init(&pool) != 0) return 1;

    void *blocks[POOL_BLOCK_COUNT];
    int ok = 1;
    for (int i = 0; i < POOL_BLOCK_COUNT; i++) {
        blocks[i] = pool_alloc(&pool);
        if (blocks[i] == NULL) { ok = 0; break; }
    }
    printf("连续分配 %d 块: %s\n", POOL_BLOCK_COUNT,
           ok ? "全部成功" : "失败（不应发生）");

    void *overflow = pool_alloc(&pool);
    printf("第 %d 块（超容量）: %s\n", POOL_BLOCK_COUNT + 1,
           overflow == NULL ? "正确返回 NULL" : "ERROR: 应返回 NULL");

    /* 释放一半后再分配 */
    for (int i = 0; i < POOL_BLOCK_COUNT / 2; i++)
        pool_free(&pool, blocks[i]);
    void *again = pool_alloc(&pool);
    printf("释放一半后重新分配: %s\n", again == NULL ? "失败" : "成功（正确）");

    pool_destroy(&pool);
    return 0;
}
