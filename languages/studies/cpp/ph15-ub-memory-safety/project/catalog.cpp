// catalog.cpp —— C++ UB 示例集：目录表 + 好版本 + 命令行入口
// 用法：./ub_catalog list | check | demos | <name> [good]
//   list    列出全部 UB 与检测工具（代码评审检查清单）
//   check   依次运行全部好版本自检（含 race 的 TSan 修复版说明），退出码 0
//   demos   循环触发坏版本（每个被 Sanitizer 中止后继续下一个）——见 Makefile
//   <name>  触发某类坏版本；<name> good 运行其好版本
// 本文件为安全代码：-Wall -Wextra 零警告；好版本全部在 Sanitizer 下零报告。
// 验证环境：Apple clang 21.0.0（c++）+ Homebrew clang 21.1.8（clang++），C++20
#include "ub_catalog.h"

#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

const Entry kEntries[] = {
    {"oob",       "越界访问（vector 下标越界）", "ASan", "运行期下标越界；at()/边界检查是正解；实测 -O0~-O2 均报告（演示统一 -O0）"},
    {"dangling",  "悬空引用（容器销毁后使用）", "ASan", "引用/迭代器由容器管理生命周期；结构性修改或销毁后一律失效"},
    {"uaf",       "use-after-free（释放后使用）", "ASan", "delete 后仍持有指针；用 unique_ptr/RAII 消灭裸 delete"},
    {"doublefree", "重复释放（double free）",   "ASan", "同一指针 delete 两次；delete 后置空（delete nullptr 合法）"},
    {"uam",       "use-after-move（moved-from 解引用）", "UBSan", "moved-from 合法但未指定；unique_ptr 保证为空，用前判空/reset"},
    {"alias",     "类型双关·严格别名",          "无运行时工具", "reinterpret_cast/union 双关是 UB；用 std::bit_cast；靠评审"},
    {"align",     "未对齐访问",                "UBSan", "强转出未对齐地址是 UB（arm64 裸跑也“只是容忍”）；memcpy 正解"},
    {"uninit",    "未初始化变量",              "编译期 -Wuninitialized", "声明即初始化 + 默认成员初始化器（ES.20）；运行时工具抓不到"},
};
const std::size_t kEntryCount = sizeof(kEntries) / sizeof(kEntries[0]);

// ---------- 好版本（安全写法） ----------

void good_oob() {
    std::vector<int> v = {1, 2, 3};
    std::printf("[good-oob] at() 越界抛 out_of_range：");
    try {
        v.at(3) = 100;
    } catch (const std::out_of_range&) {
        std::printf("caught（定义行为，未越界）\n");
    }
    std::printf("[good-oob] 合法访问 v[0..2] = %d %d %d\n", v[0], v[1], v[2]);
}

void good_dangling() {
    std::vector<std::string> names = {"motor", "pump"};
    std::string first = names[0];          // 值语义：拷贝出的副本与容器解耦
    names.clear();                         // 容器清空不影响 first
    std::printf("[good-dangling] clear() 后副本仍为 %s（无悬空）\n", first.c_str());
}

void good_uaf() {
    auto p = std::make_unique<int>(42);    // RAII：生命周期结束自动释放
    std::printf("[good-uaf] *p=%d（unique_ptr 出作用域自动释放，无 UAF 窗口）\n", *p);
}

void good_double_free() {
    int* p = new int(42);
    std::printf("[good-double-free] *p=%d\n", *p);
    delete p;
    p = nullptr;                           // delete 后立即置空
    delete p;                              // delete nullptr 合法：重复 delete 无害
    std::printf("[good-double-free] delete 后置空再 delete：无 UB\n");
}

void good_uam() {
    auto up = std::make_unique<int>(42);
    auto moved = std::move(up);
    if (up) {                              // moved-from unique_ptr 保证为空：判空再使用
        std::printf("[good-uam] *up=%d（不会走到）\n", *up);
    }
    up = std::make_unique<int>(7);         // reset/重建后恢复可用
    std::printf("[good-uam] 重建后 *up=%d，*moved=%d\n", *up, *moved);
}

void good_alias() {
    const float f = 1.0f;
    const std::uint32_t bits = std::bit_cast<std::uint32_t>(f);  // C++20 正解
    std::printf("[good-alias] bit_cast bits=%08x（定义行为）\n", bits);
}

void good_align() {
    alignas(std::uint32_t) unsigned char buf[4] = {0x44, 0x33, 0x22, 0x11};
    std::uint32_t v = 0;
    std::memcpy(&v, buf, sizeof v);        // memcpy 到对齐变量再读（黄金法则）
    std::printf("[good-align] memcpy 读出 %08x（对齐安全）\n", v);
}

void good_uninit() {
    int x = 0;                             // 声明即初始化
    struct Stats {
        int hits = 0;                      // 默认成员初始化器
        int misses = 0;
    };
    Stats s;
    std::printf("[good-uninit] x=%d s.hits=%d s.misses=%d（输出确定）\n", x, s.hits, s.misses);
}

// ---------- 命令行入口 ----------

static void run_good(const char* name) {
    if (std::strcmp(name, "oob") == 0) { good_oob(); }
    else if (std::strcmp(name, "dangling") == 0) { good_dangling(); }
    else if (std::strcmp(name, "uaf") == 0) { good_uaf(); }
    else if (std::strcmp(name, "doublefree") == 0) { good_double_free(); }
    else if (std::strcmp(name, "uam") == 0) { good_uam(); }
    else if (std::strcmp(name, "alias") == 0) { good_alias(); }
    else if (std::strcmp(name, "align") == 0) { good_align(); }
    else if (std::strcmp(name, "uninit") == 0) { good_uninit(); }
    else { std::printf("未知条目: %s\n", name); }
}

static void run_bad(const char* name) {
    if (std::strcmp(name, "oob") == 0) { bad_oob(); }
    else if (std::strcmp(name, "dangling") == 0) { bad_dangling(); }
    else if (std::strcmp(name, "uaf") == 0) { bad_uaf(); }
    else if (std::strcmp(name, "doublefree") == 0) { bad_double_free(); }
    else if (std::strcmp(name, "uam") == 0) { bad_uam(); }
    else if (std::strcmp(name, "alias") == 0) { bad_alias(); }
    else if (std::strcmp(name, "align") == 0) { bad_align(); }
    else if (std::strcmp(name, "uninit") == 0) { bad_uninit(); }
    else if (std::strcmp(name, "race") == 0) {
        std::printf("数据竞争需要 TSan 专用构建（TSan 与 ASan 不能同进程共存）：\n");
        std::printf("  make race && ./build/race_demo race\n");
    } else {
        std::printf("未知条目: %s（list 查看全部）\n", name);
    }
}

static void cmd_list() {
    std::printf("%-11s %-28s %-12s %s\n", "名称", "坑", "检测工具", "识别要点");
    for (std::size_t i = 0; i < kEntryCount; ++i) {
        std::printf("%-11s %-28s %-12s %s\n",
                    kEntries[i].name, kEntries[i].title, kEntries[i].tool, kEntries[i].howto);
    }
    std::printf("%-11s %-28s %-12s %s\n",
                "race", "数据竞争（需 TSan 构建）", "TSan", "两线程无同步写共享对象；scoped_lock/atomic 正解");
}

static int cmd_check() {
    std::printf("自检：全部好版本（ASan+UBSan 构建，零报告则退出码 0）\n");
    for (std::size_t i = 0; i < kEntryCount; ++i) {
        std::printf("[check] %s ...\n", kEntries[i].name);
        run_good(kEntries[i].name);
    }
    std::printf("自检完成: 8 个好版本全部运行, 无 Sanitizer 报告（退出码 0）\n");
    std::printf("race 好版本请单独验证: make race && ./build/race_demo good\n");
    return 0;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::printf("用法: ./ub_catalog list | check | demos | <name> [good]\n");
        return 1;
    }
    const char* cmd = argv[1];
    if (std::strcmp(cmd, "list") == 0) {
        cmd_list();
        return 0;
    }
    if (std::strcmp(cmd, "check") == 0) {
        return cmd_check();
    }
    if (std::strcmp(cmd, "demos") == 0) {
        std::printf("逐个触发坏版本请用 Makefile 的 `make demos`（每个被 Sanitizer 中止后继续）\n");
        return 0;
    }
    if (argc >= 3 && std::strcmp(argv[2], "good") == 0) {
        run_good(cmd);
        return 0;
    }
    run_bad(cmd);
    return 0;
}
