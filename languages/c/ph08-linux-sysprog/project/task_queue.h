/* task_queue.h —— 有界多生产者多消费者任务队列（mutex + condvar）
 * 一个任务 = 函数指针 + 参数; 队列关闭后 push 失败、排空后 pop 返回 0
 */
#ifndef TASK_QUEUE_H
#define TASK_QUEUE_H

#include <stddef.h>

typedef void (*task_fn)(void *arg);

typedef struct {
    task_fn fn;
    void *arg;
} task_t;

typedef struct task_queue task_queue_t;

/* 创建容量为 capacity 的队列; 失败返回 NULL */
task_queue_t *tq_create(size_t capacity);

/* 销毁队列（要求已 close 且所有消费者已退出） */
void tq_destroy(task_queue_t *q);

/* 投递任务, 队列满则阻塞等待; 队列已关闭返回 -1 */
int tq_push(task_queue_t *q, task_t task);

/* 取任务: 返回 1 取到; 返回 0 表示队列已关闭且排空 */
int tq_pop(task_queue_t *q, task_t *out);

/* 关闭队列: 不再接受 push; 已入队的任务仍会被消费完 */
void tq_close(task_queue_t *q);

#endif
