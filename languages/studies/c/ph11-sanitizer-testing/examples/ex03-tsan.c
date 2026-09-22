/* ex03-tsan.c —— TSan 抓数据竞争: 两线程无锁自增共享变量
 * 运行前提: 必须用 -fsanitize=thread 编译运行, 否则勿运行
 *   （race 模式下 counter++ 是无锁的并发读写, 属于数据竞争(UB),
 *     裸跑最终值不确定, 且可能随优化级别变化）
 * 用法: ./ex03 race | fixed
 *    race : 无锁自增 → WARNING: ThreadSanitizer: data race, 中止(退出码 134)
 *    fixed: 加互斥锁自增 → 零报告, 稳定输出 counter = 200000(退出码 0)
 * 编译: cc -Wall -Wextra -std=c11 -fsanitize=thread -g ex03-tsan.c -o ex03
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（race 报告与 fixed 输出见 README 表格与主文档示例 3）
 * 注: 锁设计与内存序分析不属于本阶段（见主文档边界声明）, 这里只用锁
 *     证明"TSan 能检测→修复后复跑零报告"的闭环。
 */
#include <pthread.h>
#include <stdio.h>
#include <string.h>

#define NITER 100000

static int counter = 0;                    /* 两个线程共享的全局变量 */
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;

/* 坏版本: 无锁自增 —— counter++ 是读-改-写三步, 两线程并发执行即竞争 */
static void *worker_race(void *arg) {
    (void)arg;
    for (int i = 0; i < NITER; i++)
        counter++;
    return NULL;
}

/* 修复版: 互斥锁串行化自增, 消除竞争 */
static void *worker_fixed(void *arg) {
    (void)arg;
    for (int i = 0; i < NITER; i++) {
        pthread_mutex_lock(&mtx);
        counter++;
        pthread_mutex_unlock(&mtx);
    }
    return NULL;
}

static void run_race(void) {
    pthread_t t1, t2;
    pthread_create(&t1, NULL, worker_race, NULL);
    pthread_create(&t2, NULL, worker_race, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("counter = %d (竞争下结果不确定)\n", counter);
}

static void run_fixed(void) {
    pthread_t t1, t2;
    pthread_create(&t1, NULL, worker_fixed, NULL);
    pthread_create(&t2, NULL, worker_fixed, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("counter = %d (加锁后稳定)\n", counter);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "用法: %s race|fixed\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "race") == 0)
        run_race();
    else if (strcmp(argv[1], "fixed") == 0)
        run_fixed();
    else {
        fprintf(stderr, "未知模式: %s\n", argv[1]);
        return 2;
    }
    return 0;
}
