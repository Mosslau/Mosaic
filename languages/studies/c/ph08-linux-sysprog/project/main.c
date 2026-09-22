/* main.c —— 演示：2 个生产者提交"区间求和"任务, 4 个工作线程消费执行,
 * 汇总结果用 mutex 保护, tq_close 优雅关闭, join 后校验总和
 */
#include "task_queue.h"

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#define PRODUCERS 2
#define WORKERS 4
#define TASKS_PER_PRODUCER 50 /* 共 100 个任务 */
#define QUEUE_CAP 16

typedef struct {
    long lo, hi;    /* 计算 lo..hi 的整数和 */
    long partial;   /* 任务自己算出局部和, 再并入全局 */
} sum_job_t;

static long g_total = 0;
static int g_done = 0;
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;

static void sum_task(void *arg) {
    sum_job_t *job = arg;
    long s = 0;
    for (long i = job->lo; i <= job->hi; i++)
        s += i;
    job->partial = s;
    pthread_mutex_lock(&g_lock);
    g_total += s;
    g_done++;
    pthread_mutex_unlock(&g_lock);
    free(job);
}

static void *producer(void *arg) {
    task_queue_t *q = arg;
    for (int i = 0; i < TASKS_PER_PRODUCER; i++) {
        sum_job_t *job = malloc(sizeof(*job));
        if (job == NULL) {
            fprintf(stderr, "内存不足\n");
            break;
        }
        job->lo = (long)i * 100 + 1;
        job->hi = job->lo + 99;
        if (tq_push(q, (task_t){sum_task, job}) != 0) {
            free(job);
            break; /* 队列已关闭 */
        }
    }
    return NULL;
}

static void *consumer(void *arg) {
    task_queue_t *q = arg;
    task_t t;
    while (tq_pop(q, &t))
        t.fn(t.arg);
    return NULL;
}

int main(void) {
    task_queue_t *q = tq_create(QUEUE_CAP);
    if (q == NULL) {
        fprintf(stderr, "创建队列失败\n");
        return 1;
    }
    pthread_t pts[PRODUCERS], cts[WORKERS];
    for (int i = 0; i < WORKERS; i++)
        pthread_create(&cts[i], NULL, consumer, q);
    for (int i = 0; i < PRODUCERS; i++)
        pthread_create(&pts[i], NULL, producer, q);
    for (int i = 0; i < PRODUCERS; i++)
        pthread_join(pts[i], NULL);
    tq_close(q); /* 生产者全部结束: 关闭队列, 消费者排空后退出 */
    for (int i = 0; i < WORKERS; i++)
        pthread_join(cts[i], NULL);

    /* 校验: 每个生产者提交 TASKS_PER_PRODUCER 段 [i*100+1, i*100+100] 的求和任务,
     * 所有生产者的区间相同, 故期望值 = PRODUCERS × 全部区间之和 */
    long expect = 0;
    for (int i = 0; i < TASKS_PER_PRODUCER; i++)
        for (long k = (long)i * 100 + 1; k <= (long)i * 100 + 100; k++)
            expect += k;
    expect *= PRODUCERS;
    printf("任务完成 %d/%d, 总和 %ld (期望 %ld): %s\n", g_done,
           PRODUCERS * TASKS_PER_PRODUCER, g_total, expect,
           g_total == expect ? "正确" : "错误");
    tq_destroy(q);
    return g_total == expect ? 0 : 1;
}
