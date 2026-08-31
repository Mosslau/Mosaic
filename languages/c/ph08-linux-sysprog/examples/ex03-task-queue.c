/* ex03-task-queue.c —— 多线程任务队列：生产者-消费者模型，mutex 保护队列、condvar 处理满/空等待 */
#define _POSIX_C_SOURCE 200809L

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define QUEUE_CAP 8
#define WORKER_NUM 3
#define TASK_NUM 20

typedef struct {
    int *items;
    int head, tail, count;
    pthread_mutex_t lock;
    pthread_cond_t not_empty; /* 队列非空: 消费者可取 */
    pthread_cond_t not_full;  /* 队列未满: 生产者可放 */
} TaskQueue;

static void tq_init(TaskQueue *q) {
    q->items = malloc(QUEUE_CAP * sizeof(int));
    q->head = q->tail = q->count = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);
}

static void tq_destroy(TaskQueue *q) {
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->not_empty);
    pthread_cond_destroy(&q->not_full);
    free(q->items);
}

static void tq_push(TaskQueue *q, int task) {
    pthread_mutex_lock(&q->lock);
    while (q->count == QUEUE_CAP) /* 满则等, while 防虚假唤醒 */
        pthread_cond_wait(&q->not_full, &q->lock);
    q->items[q->tail] = task;
    q->tail = (q->tail + 1) % QUEUE_CAP;
    q->count++;
    pthread_cond_signal(&q->not_empty); /* 通知消费者 */
    pthread_mutex_unlock(&q->lock);
}

static int tq_pop(TaskQueue *q) {
    pthread_mutex_lock(&q->lock);
    while (q->count == 0)
        pthread_cond_wait(&q->not_empty, &q->lock);
    int task = q->items[q->head];
    q->head = (q->head + 1) % QUEUE_CAP;
    q->count--;
    pthread_cond_signal(&q->not_full); /* 通知生产者 */
    pthread_mutex_unlock(&q->lock);
    return task;
}

static void *worker(void *arg) {
    TaskQueue *q = arg;
    for (;;) {
        int task = tq_pop(q);
        if (task < 0)
            break; /* -1 为终止信号 */
        printf("worker %lu 处理任务 %d\n", (unsigned long)pthread_self(), task);
        struct timespec ts = {0, 10 * 1000 * 1000}; /* 10ms, 模拟耗时 */
        nanosleep(&ts, NULL);
    }
    return NULL;
}

int main(void) {
    TaskQueue q;
    tq_init(&q);
    pthread_t workers[WORKER_NUM];
    for (int i = 0; i < WORKER_NUM; i++)
        pthread_create(&workers[i], NULL, worker, &q);
    for (int i = 0; i < TASK_NUM; i++) /* 生产者: 投递 20 个任务 */
        tq_push(&q, i);
    for (int i = 0; i < WORKER_NUM; i++) /* 再投 3 个终止信号 */
        tq_push(&q, -1);
    for (int i = 0; i < WORKER_NUM; i++)
        pthread_join(workers[i], NULL); /* 全部 worker 退出 */
    printf("所有 worker 已退出\n");
    tq_destroy(&q);
    return 0;
}
