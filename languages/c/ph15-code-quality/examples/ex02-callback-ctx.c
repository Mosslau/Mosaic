// examples/ex02-callback-ctx.c —— 函数指针/回调：上下文约定 + 回调顺序实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex02-callback-ctx.c -o ex02
// 运行：./ex02（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdio.h>

/* ===== 1. 函数指针基础 ===== */

/* 一元数学运算的"函数指针"形态：double (*)(double) */
typedef double (*unary_fn)(double);

static double twice(double x)  { return x * 2.0; }
static double square(double x) { return x * x; }
static double identity(double x) { return x; }

/* 函数指针作为参数：把"怎么变换"交给调用者（策略模式的最简形态） */
static double apply(unary_fn f, double x) {
    return f(x);
}

/* 函数指针数组 + 表驱动：ops[i] 按索引选策略 */
static unary_fn g_ops[3] = { identity, twice, square };

static void demo_funptr(void) {
    printf("函数指针传参: apply(twice,21)=%.0f  apply(square,6)=%.0f\n",
           apply(twice, 21.0), apply(square, 6.0));
    printf("函数指针数组: ops[0](7)=%.0f  ops[1](7)=%.0f  ops[2](7)=%.0f\n",
           g_ops[0](7.0), g_ops[1](7.0), g_ops[2](7.0));
}

/* ===== 2. 回调 + 上下文约定 ===== */

/* 回调签名：回调要"记住"的数据装进 void *ctx 传回。
 * 约定（roadmap 必会概念）：ctx 由注册者提供并负责生命周期——回调只读用、
 * 不释放；注册者必须保证 ctx 存活到"注销/不再回调"之后。 */
typedef void (*event_cb)(int ev, void *ctx);

#define MAX_HANDLERS 8
#define EV_KEY 1
#define EV_TIMER 2

/* 事件分发器：内部只存"函数指针 + ctx"对，不关心回调业务 */
typedef struct {
    event_cb fn;
    void *ctx;
} handler_t;

static handler_t g_handlers[MAX_HANDLERS];
static int g_nhandlers = 0;

static int event_register(event_cb fn, void *ctx) {
    if (g_nhandlers >= MAX_HANDLERS)
        return -1;                       /* 满: 返回错误码而非静默丢弃 */
    g_handlers[g_nhandlers].fn = fn;
    g_handlers[g_nhandlers].ctx = ctx;
    g_nhandlers++;
    return 0;
}

static void event_fire(int ev) {
    for (int i = 0; i < g_nhandlers; i++) /* 按注册顺序回调 */
        g_handlers[i].fn(ev, g_handlers[i].ctx);
}

/* ---- 回调实现：各自还原自己的 ctx 类型 ---- */

struct key_ctx { const char *name; int count; };  /* 回调私有状态 */

static void key_handler(int ev, void *ctx) {
    (void)ev;
    struct key_ctx *k = (struct key_ctx *)ctx;    /* ctx 还原回自己的类型 */
    k->count++;
    printf("  key_handler[%s]: 收到事件, 累计 %d 次\n", k->name, k->count);
}

static void timer_handler(int ev, void *ctx) {
    (void)ev;
    long *ticks = (long *)ctx;                    /* ctx 也可以只是一个计数变量 */
    (*ticks)++;
    printf("  timer_handler: 累计 tick = %ld\n", *ticks);
}

static void demo_callback(void) {
    struct key_ctx a = {"A", 0};
    struct key_ctx b = {"B", 0};
    long ticks = 0;

    /* 注册顺序 A → timer → B；ctx 是栈上局部变量, 生命周期 = 本函数执行期间 */
    event_register(key_handler, &a);
    event_register(timer_handler, &ticks);
    event_register(key_handler, &b);

    printf("回调演示 1: 触发 EV_KEY（应看到 A → timer → B 顺序）:\n");
    event_fire(EV_KEY);

    printf("回调演示 2: 触发 EV_TIMER:\n");
    event_fire(EV_TIMER);

    printf("回调演示 3: 再触发 EV_KEY（A/B 的 count 与 timer 的 ticks 持续累计,"
           "\n          证明 ctx 状态跨事件保留, 且三个回调各自隔离）:\n");
    event_fire(EV_KEY);
}

int main(void) {
    printf("=== ex02 函数指针与回调 ===\n");
    demo_funptr();
    demo_callback();
    printf("ctx 约定: 谁注册谁负责 ctx 生命周期; 本示例 ctx 为栈变量,"
           " 函数结束即失效——注册者必须保证存活期\n");
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex02 函数指针与回调 ===
 * 函数指针传参: apply(twice,21)=42  apply(square,6)=36
 * 函数指针数组: ops[0](7)=7  ops[1](7)=14  ops[2](7)=49
 * 回调演示 1: 触发 EV_KEY（应看到 A → timer → B 顺序）:
 *   key_handler[A]: 收到事件, 累计 1 次
 *   timer_handler: 累计 tick = 1
 *   key_handler[B]: 收到事件, 累计 1 次
 * 回调演示 2: 触发 EV_TIMER:
 *   key_handler[A]: 收到事件, 累计 2 次
 *   timer_handler: 累计 tick = 2
 *   key_handler[B]: 收到事件, 累计 2 次
 * 回调演示 3: 再触发 EV_KEY（A/B 的 count 与 timer 的 ticks 持续累计,
 *           证明 ctx 状态跨事件保留, 且三个回调各自隔离）:
 *   key_handler[A]: 收到事件, 累计 3 次
 *   timer_handler: 累计 tick = 3
 *   key_handler[B]: 收到事件, 累计 3 次
 * ctx 约定: 谁注册谁负责 ctx 生命周期; 本示例 ctx 为栈变量, 函数结束即失效——注册者必须保证存活期
 */
