/* ex01-c-main.c —— C 主程序调用 libcalc 动态库（对照组：其他语言调用同一库）
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
 *   cc -Wall -Wextra -std=c11 ex01-c-main.c -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex01
 * 运行：/tmp/ph14-ex/ex01
 * 导出符号检查（nm 实测，见 examples/README）：
 *   nm -gU /tmp/ph14-ex/libcalc.dylib   # 只看全局导出（T = 文本段可调用）
 */
#include <stdio.h>

#include "calc.h"

int main(void) {
    int32_t sum = calc_add(20, 22);
    int32_t prod = calc_mul(6, 7);
    int32_t q = 0;
    int rc = calc_div(84, 2, &q);
    int32_t n = calc_strlen("hello");

    printf("calc_add(20,22) = %d\n", (int)sum);
    printf("calc_mul(6,7)   = %d\n", (int)prod);
    printf("calc_div(84,2)  = rc=%d q=%d\n", rc, (int)q);
    printf("calc_div(1,0)   = rc=%d（除零错误码, q 未被改写）\n",
           calc_div(1, 0, &q));
    printf("calc_strlen(hello) = %d\n", (int)n);
    return 0;
}
