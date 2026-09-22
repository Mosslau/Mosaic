// 来源：04-memory-mgmt.md 第 6 章示例 3 —— 简单固定块内存池
// 核心思想：一次申请大块内存，切分成固定大小 slot，分配/释放只操作空闲链表，O(1) 且避免频繁系统调用
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex03-mem-pool.c -o ex03-mem-pool
// 运行：./ex03-mem-pool
// 验证状态：已验证
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

#define POOL_BLOCK_SIZE 32
#define POOL_BLOCK_COUNT 8

typedef struct Block {
    struct Block *next;               /* 空闲链表指针 */
    char          data[POOL_BLOCK_SIZE]; /* 用户数据区 */
} Block;

typedef struct {
    Block *free_list;   /* 空闲链表头 */
    Block *chunk;       /* 整块申请，用于整体释放 */
} MemPool;

int pool_init(MemPool *pool) {
    pool->chunk = malloc(POOL_BLOCK_COUNT * sizeof(Block));
    if (pool->chunk == NULL) return -1;
    /* 将所有 block 串成空闲链表 */
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
    if (pool->free_list == NULL) return NULL;  /* 池已空 */
    Block *blk = pool->free_list;
    pool->free_list = blk->next;
    return blk->data;
}

void pool_free(MemPool *pool, void *ptr) {
    if (ptr == NULL) return;
    /* 通过 ptr 反推 Block 起始地址 */
    Block *blk = (Block *)((char *)ptr - offsetof(Block, data));
    blk->next = pool->free_list;
    pool->free_list = blk;
}

int main(void) {
    MemPool pool;
    if (pool_init(&pool) != 0) {
        fprintf(stderr, "内存池初始化失败\n");
        return 1;
    }
    void *a = pool_alloc(&pool);
    void *b = pool_alloc(&pool);
    printf("分配 2 块: a=%p, b=%p\n", a, b);

    pool_free(&pool, a);
    pool_free(&pool, b);
    printf("释放后空闲链表头: %p\n", (void *)pool.free_list);

    /* 耗尽池中所有块 */
    for (int i = 0; i < POOL_BLOCK_COUNT; i++)
        pool_alloc(&pool);
    void *overflow = pool_alloc(&pool);
    printf("超容量分配: %s\n",
           overflow == NULL ? "正确返回 NULL" : "ERROR: 应返回 NULL");

    pool_destroy(&pool);
    return 0;
}
