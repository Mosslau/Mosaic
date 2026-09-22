/* sol-05-coverage.c —— 参考实现: 生成覆盖率报告并补测
 * 第一版(只跑合法路径)的实测覆盖(Apple clang 21.0.0 + Apple gcov, macOS;
 * 本机 .gcda 名带可执行名前缀 sol05-sol-05-coverage.gcda, Linux gcc 直接
 * 是 sol-05-coverage.gcda):
 *   Lines executed:72.73% of 22      ← report_corrupt 的行显示 #####
 *   Branches executed:100.00% of 10
 *   Taken at least once:70.00% of 10 ← check_len 的错误分支 taken 0%
 * 补测后(本文件的 full 模式)实测:
 *   Lines executed:100.00% of 22
 *   Branches executed:100.00% of 10
 *   Taken at least once:100.00% of 10
 * 覆盖率的用途是指引补测, 不是数字本身——报告里的 ##### 与 taken 0%
 * 就是"没测到的路径"清单。
 */
// 验证环境：Apple clang 21.0.0（cc）+ Apple gcov（/usr/bin/gcov），macOS（Darwin arm64）
// 编译：cc --coverage -g sol-05-coverage.c -o sol05（--coverage 即插桩编译）
// 运行：./sol05                → 第一版路径(只走合法路径)
//       ./sol05 full           → 补测版(触发错误分支 + 调用 report_corrupt)
// 报告：gcov sol05-sol-05-coverage.gcda / gcov -b sol05-sol-05-coverage.gcda（macOS 名; Linux 用 sol-05-coverage.gcda）
// 验证状态：已验证（第一版与补测版的覆盖数字见 README 表格与主文档示例 6 补测练习）
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static int is_leap(int y) {
    if (y % 400 == 0) return 1;
    if (y % 100 == 0) return 0;
    return y % 4 == 0;
}

/* 模拟 record 长度校验(衔接 ph12): len > max 是错误路径 */
static int check_len(size_t len, size_t max) {
    if (len > max) return -1;    /* 错误路径: 第一版故意不触发 */
    return 0;
}

/* 损坏处理函数: 第一版从不调用 → 行覆盖出现 #####。
 * 注意不能写 static: 未调用的 static 函数会被编译器剔除、不参与覆盖统计。 */
void report_corrupt(void) {
    fprintf(stderr, "record corrupt\n");
}

int main(int argc, char **argv) {
    int full = argc > 1 && strcmp(argv[1], "full") == 0;

    printf("%d %d %d %d\n",
           is_leap(2000), is_leap(1900), is_leap(2024), is_leap(2023));
    printf("check_len ok=%d\n", check_len(4, 16));   /* 只走合法路径 */

    if (full) {
        printf("check_len bad=%d\n", check_len(20, 16)); /* 补测: 错误分支 */
        report_corrupt();                                /* 补测: 未测函数 */
    }
    return 0;
}
