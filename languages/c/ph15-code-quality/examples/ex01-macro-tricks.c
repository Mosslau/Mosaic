// examples/ex01-macro-tricks.c —— 宏技巧：副作用陷阱/do-while(0)/可变参宏/X-Macro（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex01-macro-tricks.c -o ex01
// 运行：./ex01（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdio.h>

/* ============ 区 1：副作用陷阱正反例 ============ */

/* 反例：宏参数只加括号不够 —— 展开后参数表达式被求值多次。
 * MAX_BAD(i++, 10) 展开为 ((i++) > (10) ? (i++) : (10))：i++ 出现了两次。 */
#define MAX_BAD(a, b) ((a) > (b) ? (a) : (b))

/* 正解：要"函数语义"就别用宏 —— static inline 函数参数只求值一次。
 * （此处演示用 int 版，见主文档 3.1：类型泛化要靠 _Generic/宏工厂，同样要避开副作用） */
static inline int imax(int a, int b) {
    return a > b ? a : b;
}

static void demo_side_effect(void) {
    int i = 1;
    /* MAX_BAD(i++, 0)：i 从 1 开始, 比较处求值一次变 2, 真分支里再求值一次变 3 ——
     * 宏里的 i++ 一共被求值两次, 返回的是第二次的值 2 */
    int bad = MAX_BAD(i++, 0);
    printf("区1 反例: MAX_BAD(i++,0)   i 从 %d 变到 %d (结果=%d)  ← i++ 求值两次\n",
           1, i, bad);

    i = 1;
    int good = imax(i++, 0);         /* 函数参数只求值一次 */
    printf("区1 正例: imax(i++,0)     i 从 %d 变到 %d (结果=%d)  ← 只求值一次\n",
           1, i, good);
}

/* ============ 区 2：do-while(0) ============ */

/* 反例：块语句宏没有 do-while(0) 包裹，else 会挂错 */
#define SWAP_BAD(a, b) \
    { int t_ = (a); (a) = (b); (b) = t_; }

/* 正例：do{...}while(0) 让宏在语法上等价于"一条语句"，可安全跟 else */
#define SWAP(a, b) \
    do { int t_ = (a); (a) = (b); (b) = t_; } while (0)

static void demo_do_while(void) {
    int x = 1, y = 2, z = 0;

    if (x > y)
        SWAP(x, y);        /* 正例: 宏整体是一条语句, else 正确归属 if */
    else
        z = 1;
    printf("区2 do-while(0): if/else 下 x=%d y=%d z=%d (SWAP 未执行, else 分支正确)\n",
           x, y, z);

    if (x < y)
        SWAP(x, y);        /* 条件为真执行 swap */
    printf("区2 do-while(0): 再换一次 x=%d y=%d (swap 生效)\n", x, y);

#if 0   /* 反例被注释：SWAP_BAD 在 if/else 里编译报错（语法错乱）, 取消注释即见 */
    if (x > y)
        SWAP_BAD(x, y);
    else
        z = 2;
#endif
}

/* ============ 区 3：可变参宏 ============ */

/* 注释：ISO C11 的 ... 至少要有一个实参。用 GNU/Clang 的 "##" 逗号吞并扩展
 * （本仓库工具链 gcc/clang 均支持）可以让零实参调用也合法；
 * C23 提供了标准化的 __VA_OPT__(,) 代替。两种写法效果相同。 */
#define LOG(fmt, ...) \
    printf("[%s:%d] " fmt "\n", __FILE__, __LINE__, ##__VA_ARGS__)

static void demo_variadic(void) {
    int code = 42;
    LOG("零个可变实参也合法 (##__VA_ARGS__)");
    LOG("带可变实参: code=%d", code);
    printf("区3 说明: LOG 宏 = 自动 file:line + 转发 __VA_ARGS__, 见上方两行前缀\n");
}

/* ============ 区 4：X-Macro ============ */

/* 1) 先定义"表格"宏：每行是一个占位调用 X(...) */
#define ERROR_TABLE(X)      \
    X(ERR_OK,       "ok")   \
    X(ERR_BADARG,   "bad argument") \
    X(ERR_NOTFOUND, "not found")    \
    X(ERR_NOMEM,    "out of memory")

/* 2) 定义 X 的一次展开规则, 然后展开表格 → 生成枚举 */
#define ERROR_DEF_ENUM(name, msg) name,
typedef enum { ERROR_TABLE(ERROR_DEF_ENUM) ERR_COUNT } err_t;
#undef ERROR_DEF_ENUM

/* 3) 换一个 X 展开规则 → 生成字符串表（顺序与枚举一致） */
#define ERROR_DEF_STR(name, msg) msg,
static const char *const err_strs[] = { ERROR_TABLE(ERROR_DEF_STR) };
#undef ERROR_DEF_STR

/* 4) 查找函数也能由同一张表"间接生成"的认知：表是唯一事实源,
 *    枚举/字符串/查找三处永远同步（增删一行错误码, 无需改三处） */
static const char *err_str(err_t e) {
    if ((int)e < 0 || (int)e >= ERR_COUNT)
        return "unknown error";
    return err_strs[e];
}

static void demo_xmacro(void) {
    printf("区4 X-Macro: ERR_NOTFOUND=%d, 字符串=\"%s\"\n",
           (int)ERR_NOTFOUND, err_str(ERR_NOTFOUND));
    printf("区4 X-Macro: 字符串表共 %d 项, 与枚举一一对应 (同一张 ERROR_TABLE 生成)\n",
           ERR_COUNT);
}

/* ============ 条件编译：标准版本与平台自述 ============ */

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
#define C_STANDARD "C11"
#elif defined(__STDC_VERSION__)
#define C_STANDARD "C99"
#else
#define C_STANDARD "pre-C99"
#endif

#if defined(__APPLE__)
#define PLATFORM "Apple (macOS)"
#elif defined(__linux__)
#define PLATFORM "Linux"
#elif defined(_WIN32)
#define PLATFORM "Windows"
#else
#define PLATFORM "unknown"
#endif

int main(void) {
    printf("=== ex01 宏技巧 ===\n");
    demo_side_effect();
    demo_do_while();
    demo_variadic();
    demo_xmacro();
    printf("条件编译: 标准=%s 平台=%s (编译期由宏决定)\n", C_STANDARD, PLATFORM);
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex01 宏技巧 ===
 * 区1 反例: MAX_BAD(i++,0)   i 从 1 变到 3 (结果=2)  ← i++ 求值两次
 * 区1 正例: imax(i++,0)     i 从 1 变到 2 (结果=1)  ← 只求值一次
 * 区2 do-while(0): if/else 下 x=1 y=2 z=1 (SWAP 未执行, else 分支正确)
 * 区2 do-while(0): 再换一次 x=2 y=1 (swap 生效)
 * [ex01-macro-tricks.c:75] 零个可变实参也合法 (##__VA_ARGS__)
 * [ex01-macro-tricks.c:76] 带可变实参: code=42
 * 区3 说明: LOG 宏 = 自动 file:line + 转发 __VA_ARGS__, 见上方两行前缀
 * 区4 X-Macro: ERR_NOTFOUND=2, 字符串="not found"
 * 区4 X-Macro: 字符串表共 4 项, 与枚举一一对应 (同一张 ERROR_TABLE 生成)
 * 条件编译: 标准=C11 平台=Apple (macOS) (编译期由宏决定)
 */
