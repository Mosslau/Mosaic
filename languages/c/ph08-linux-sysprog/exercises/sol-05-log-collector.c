/* sol-05-log-collector.c —— 日志采集程序：多线程生产日志 → 有界队列 → 单写线程 O_APPEND 落盘
 * 用法: ./sol-05 [日志文件]   默认 ph05 风格文件名 app.log
 * 验证: 行数 == PRODUCERS * LINES_PER, 无丢行无重复
 */
#define _POSIX_C_SOURCE 200809L

#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define QUEUE_CAP 16
#define PRODUCERS 4
#define LINES_PER 250 /* 每线程生产 250 行, 共 1000 行 */
#define LINE_SIZE 128

typedef struct {
    char lines[QUEUE_CAP][LINE_SIZE];
    int head, tail, count;
    int done_producers; /* 已结束的生产者数量 */
    pthread_mutex_t lock;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
} LogQueue;

static LogQueue g_q;

static void lq_init(LogQueue *q) {
    q->head = q->tail = q->count = q->done_producers = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);
}

static void lq_push(LogQueue *q, const char *line) {
    pthread_mutex_lock(&q->lock);
    while (q->count == QUEUE_CAP) /* 满则等, while 防虚假唤醒 */
        pthread_cond_wait(&q->not_full, &q->lock);
    snprintf(q->lines[q->tail], LINE_SIZE, "%s", line);
    q->tail = (q->tail + 1) % QUEUE_CAP;
    q->count++;
    pthread_cond_signal(&q->not_empty);
    pthread_mutex_unlock(&q->lock);
}

/* 返回 1 取到一行; 返回 0 表示全部生产者已结束且队列已空 */
static int lq_pop(LogQueue *q, char *out) {
    pthread_mutex_lock(&q->lock);
    while (q->count == 0 && q->done_producers < PRODUCERS)
        pthread_cond_wait(&q->not_empty, &q->lock);
    if (q->count == 0) { /* 所有生产者结束且队列空 */
        pthread_mutex_unlock(&q->lock);
        return 0;
    }
    snprintf(out, LINE_SIZE, "%s", q->lines[q->head]);
    q->head = (q->head + 1) % QUEUE_CAP;
    q->count--;
    pthread_cond_signal(&q->not_full);
    pthread_mutex_unlock(&q->lock);
    return 1;
}

static void producer_done(LogQueue *q) {
    pthread_mutex_lock(&q->lock);
    q->done_producers++;
    pthread_cond_signal(&q->not_empty); /* 唤醒可能等待的消费者 */
    pthread_mutex_unlock(&q->lock);
}

static void *producer(void *arg) {
    long id = (long)arg;
    char line[LINE_SIZE];
    for (int i = 0; i < LINES_PER; i++) {
        snprintf(line, sizeof line, "[producer-%ld] seq=%d ts=%ld\n", id, i, (long)time(NULL));
        lq_push(&g_q, line);
    }
    producer_done(&g_q);
    return NULL;
}

static void *writer(void *arg) {
    const char *path = arg;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644); /* O_APPEND: 重启后不覆盖 */
    if (fd < 0) {
        perror("open");
        return NULL;
    }
    char line[LINE_SIZE];
    long written = 0;
    while (lq_pop(&g_q, line)) {
        size_t len = strlen(line);
        size_t off = 0;
        while (off < len) { /* 短写处理 */
            ssize_t w = write(fd, line + off, len - off);
            if (w < 0) {
                perror("write");
                close(fd);
                return NULL;
            }
            off += (size_t)w;
        }
        written++;
    }
    close(fd);
    printf("写线程落盘 %ld 行\n", written);
    return NULL;
}

int main(int argc, char *argv[]) {
    const char *path = argc > 1 ? argv[1] : "app.log";
    lq_init(&g_q);
    pthread_t wt, pts[PRODUCERS];
    pthread_create(&wt, NULL, writer, (void *)path);
    for (long i = 0; i < PRODUCERS; i++)
        pthread_create(&pts[i], NULL, producer, (void *)i);
    for (int i = 0; i < PRODUCERS; i++)
        pthread_join(pts[i], NULL);
    pthread_join(wt, NULL);
    printf("完成: 预期 %d 行, 请用 wc -l %s 验证\n", PRODUCERS * LINES_PER, path);
    return 0;
}
