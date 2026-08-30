// 来源：project/ —— report.h 结果输出模块接口
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#ifndef REPORT_H
#define REPORT_H

#include "parse.h"

/* 打印单个文件的统计（verbose=1 时带明细） */
void report_print(const char *filename, const Stats *stats, int verbose);

/* 打印多个文件的汇总 */
void report_print_total(const Stats *total, int file_count);

#endif /* REPORT_H */
