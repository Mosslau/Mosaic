/* calc.c —— 动态库实现（编译为 libcalc.dylib / libcalc.so / calc.dll）
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
 * 编译（Linux，符号默认全部导出，无需 -fvisibility=hidden 也能被调用）：
 *   cc -Wall -Wextra -std=c11 -shared -fPIC calc.c -o /tmp/ph14-ex/libcalc.so
 */
#include "calc.h"

#include <stddef.h>     /* NULL */

int32_t calc_add(int32_t a, int32_t b) {
    return a + b;
}

int32_t calc_mul(int32_t a, int32_t b) {
    return a * b;
}

int calc_div(int32_t a, int32_t b, int32_t *out) {
    if (b == 0 || out == NULL)
        return -1;              /* 错误码：0 成功，负数错误 */
    *out = a / b;
    return 0;
}

int32_t calc_strlen(const char *s) {
    if (s == NULL)
        return -1;              /* 空指针：返回错误码而非解引用崩溃 */
    int32_t n = 0;
    while (s[n] != '\0')
        n++;
    return n;
}
