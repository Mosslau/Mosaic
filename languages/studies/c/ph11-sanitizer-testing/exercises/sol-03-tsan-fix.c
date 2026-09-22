/* sol-03-tsan-fix.c —— 参考实现: 用 TSan 检测并修复数据竞争
 * 坏版本(两线程无锁自增共享 counter)的实测报告(Apple clang 21.0.0,
 * cc -Wall -Wextra -std=c11 -fsanitize=thread -g):
 *   WARNING: ThreadSanitizer: data race (pid=...)
 *     Location is global 'counter' at ... (sol03+0x...)
 *   SUMMARY: ThreadSanitizer: data race (...) in worker_race+0x...
 *   ThreadSanitizer: reported 1 warnings
 *   （退出码 134; 竞争下 counter 最终值不确定, 实测一次为 102147）
 * 修复思路: 用互斥锁把"读-改-写"串行化——本阶段只要求会用工具检测与修复,
 *   锁设计与内存序分析属于并发专题(见主文档边界声明), 这里不展开。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=thread -g sol-03-tsan-fix.c -o sol03
// 运行：./sol03（输出 counter = 200000 (加锁后稳定), 退出码 0）
// 验证状态：已验证（坏版本 data race 报告实测; 修复版零报告, 退出码 0）
#include <pthread.h>
#include <stdio.h>

#define NITER 100000

static int counter = 0;                    /* 两线程共享的全局变量 */
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;

static void *worker(void *arg) {
    (void)arg;
    for (int i = 0; i < NITER; i++) {
        pthread_mutex_lock(&mtx);          /* 修复: 加锁串行化自增 */
        counter++;
        pthread_mutex_unlock(&mtx);
    }
    return NULL;
}

int main(void) {
    pthread_t t1, t2;
    pthread_create(&t1, NULL, worker, NULL);
    pthread_create(&t2, NULL, worker, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("counter = %d (加锁后稳定)\n", counter);
    return 0;
}
