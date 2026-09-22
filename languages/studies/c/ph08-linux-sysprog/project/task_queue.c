/* task_queue.c —— 环形缓冲实现; 所有共享读写都持锁, 等待一律 while 重查防虚假唤醒 */
#include "task_queue.h"

#include <pthread.h>
#include <stdlib.h>

struct task_queue {
    task_t *buf;
    size_t cap;
    size_t head, tail, count;
    int closed;
    pthread_mutex_t lock;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
};

task_queue_t *tq_create(size_t capacity) {
    if (capacity == 0)
        return NULL;
    task_queue_t *q = malloc(sizeof(*q));
    if (q == NULL)
        return NULL;
    q->buf = malloc(capacity * sizeof(task_t));
    if (q->buf == NULL) {
        free(q);
        return NULL;
    }
    q->cap = capacity;
    q->head = q->tail = q->count = 0;
    q->closed = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);
    return q;
}

void tq_destroy(task_queue_t *q) {
    if (q == NULL)
        return;
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->not_empty);
    pthread_cond_destroy(&q->not_full);
    free(q->buf);
    free(q);
}

int tq_push(task_queue_t *q, task_t task) {
    pthread_mutex_lock(&q->lock);
    while (q->count == q->cap && !q->closed)
        pthread_cond_wait(&q->not_full, &q->lock);
    if (q->closed) {
        pthread_mutex_unlock(&q->lock);
        return -1;
    }
    q->buf[q->tail] = task;
    q->tail = (q->tail + 1) % q->cap;
    q->count++;
    pthread_cond_signal(&q->not_empty);
    pthread_mutex_unlock(&q->lock);
    return 0;
}

int tq_pop(task_queue_t *q, task_t *out) {
    pthread_mutex_lock(&q->lock);
    while (q->count == 0 && !q->closed)
        pthread_cond_wait(&q->not_empty, &q->lock);
    if (q->count == 0) { /* 已关闭且排空 */
        pthread_mutex_unlock(&q->lock);
        return 0;
    }
    *out = q->buf[q->head];
    q->head = (q->head + 1) % q->cap;
    q->count--;
    pthread_cond_signal(&q->not_full);
    pthread_mutex_unlock(&q->lock);
    return 1;
}

void tq_close(task_queue_t *q) {
    pthread_mutex_lock(&q->lock);
    q->closed = 1;
    pthread_cond_broadcast(&q->not_empty); /* 唤醒全部等待中的消费者 */
    pthread_cond_broadcast(&q->not_full);  /* 唤醒全部等待中的生产者 */
    pthread_mutex_unlock(&q->lock);
}
