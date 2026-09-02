// ub_catalog.h —— C++ UB 示例集：目录表与坏/好版本声明
#ifndef UB_CATALOG_H
#define UB_CATALOG_H

#include <cstddef>

// 目录条目：name（命令行名）/ title（中文名）/ tool（检测工具）/ howto（识别要点）
struct Entry {
    const char* name;
    const char* title;
    const char* tool;
    const char* howto;
};

extern const Entry kEntries[];
extern const std::size_t kEntryCount;

// 坏版本（bad_demos.cpp 实现，故意出错 —— 全部为 UB 演示，勿裸跑）
void bad_oob();
void bad_dangling();
void bad_uaf();
void bad_double_free();
void bad_uam();
void bad_alias();
void bad_align();
void bad_uninit();

// 好版本（catalog.cpp 实现，安全写法）
void good_oob();
void good_dangling();
void good_uaf();
void good_double_free();
void good_uam();
void good_alias();
void good_align();
void good_uninit();

#endif  // UB_CATALOG_H
