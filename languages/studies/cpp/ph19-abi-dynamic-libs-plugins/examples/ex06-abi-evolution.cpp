// examples/ex06-abi-evolution.cpp —— ABI 演进仿真（二进制兼容 vs 源码兼容）
// 教学点：roadmap 学习内容「版本兼容」。动态库升级时，接口有两种改法——
//   · 尾部追加字段 / 新增函数 → 老宿主仍按老布局/老符号工作 = 二进制兼容
//   · 头部/中间插入字段、改字段类型、改函数签名 → 老宿主读错位置 = 二进制不兼容
// 本文件在单一翻译单元里仿真「同一 struct 的两个演进版本」，用 offsetof 与
// 逐字节读取证明：尾部追加保持老字段偏移不变（老宿主无恙），中间插入把后续
// 字段全部移位（老宿主按老偏移读到脏数据）。并演示插件边界常用的
//「接口版本号 + major/minor 兼容规则」——宿主在加载后、使用前先校验版本。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：clang++ -std=c++20 -Wall -Wextra ex06-abi-evolution.cpp -o /tmp/ph19cpp-ex06
// 运行：/tmp/ph19cpp-ex06
// 验证状态：已验证（双编译器实测：编译零警告、运行通过、断言全绿、退出码 0）

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

// —— 三种「接口结构」版本 ——

// v1：宿主 v1.0 编译时看到的形状
struct info_v1 {
    std::int32_t api;   // 偏移 0
    std::int32_t kind;  // 偏移 4
};

// v2a：尾部追加（推荐的演进方向）：老字段 api/kind 偏移不变
struct info_v2_tail {
    std::int32_t api;    // 偏移 0（不变）
    std::int32_t kind;   // 偏移 4（不变）
    std::int64_t flags;  // 偏移 8（新增，老宿主从不读）
};

// v2b：头部插入（破坏性的演进方向）：老字段被整体推到后面，偏移全变
struct info_v2_mid {
    std::int64_t flags;  // 偏移 0（新字段插在最前）
    std::int32_t api;    // 偏移 8（原本在 0！）
    std::int32_t kind;   // 偏移 12（原本在 4！）
};

// 老宿主读 api 的固定假设：偏移 0、宽 4 字节（它只认识 info_v1）
std::int32_t old_host_read_api(const void* plugin_blob) {
    std::int32_t api = 0;
    std::memcpy(&api, plugin_blob, sizeof(api));
    return api;
}

// —— 插件接口版本约定（真实插件边界的通用模式）——

struct plugin_version {
    std::int32_t major;
    std::int32_t minor;
};

// 兼容规则（常见约定）：major 变 = 二进制不兼容，宿主必须拒绝加载；
// major 相同 = 尾部追加式演进允许，宿主可直接使用（本函数只判 major）。
// 若需要「某些能力至少要到某 minor」，可再加 minor 门槛。
bool is_compatible(const plugin_version& host_need, const plugin_version& plugin_have) {
    return host_need.major == plugin_have.major && plugin_have.minor >= host_need.minor;
}

}  // namespace

int main() {
    std::printf("=== struct 布局对照（offsetof） ===\n");
    std::printf("info_v1       : sizeof=%zu  api@%zu  kind@%zu\n", sizeof(info_v1),
                offsetof(info_v1, api), offsetof(info_v1, kind));
    std::printf("info_v2_tail  : sizeof=%zu  api@%zu  kind@%zu  flags@%zu\n", sizeof(info_v2_tail),
                offsetof(info_v2_tail, api), offsetof(info_v2_tail, kind),
                offsetof(info_v2_tail, flags));
    std::printf("info_v2_mid   : sizeof=%zu  api@%zu  kind@%zu  flags@%zu\n", sizeof(info_v2_mid),
                offsetof(info_v2_mid, api), offsetof(info_v2_mid, kind),
                offsetof(info_v2_mid, flags));

    std::printf("\n=== 老宿主（只认 info_v1，api 在偏移 0）读升级后的插件数据 ===\n");

    // 尾部追加版：插件实际 api=2，kind=7
    const info_v2_tail upgraded_tail{/*api=*/2, /*kind=*/7, /*flags=*/0x1122334455667788LL};
    const auto tail_read = old_host_read_api(&upgraded_tail);
    std::printf("  v2_tail  -> 老宿主读到 api = %d（正确：尾部追加没动老字段）\n", tail_read);

    // 头部插入版：同一份数据语义，只是新字段插在前面
    const info_v2_mid upgraded_mid{/*flags=*/0x1122334455667788LL, /*api=*/2, /*kind=*/7};
    const auto mid_read = old_host_read_api(&upgraded_mid);
    std::printf("  v2_mid   -> 老宿主读到 api = %d（错误！flags 低 32 位 0x%x 被当成 api）\n",
                mid_read, 0x55667788);

    std::printf("\n=== 插件边界版本检查（major 决定二进制兼容） ===\n");
    const plugin_version host_need{/*major=*/2, /*minor=*/1};
    const plugin_version plugin_2_0{2, 0};
    const plugin_version plugin_2_5{2, 5};
    const plugin_version plugin_3_0{3, 0};
    std::printf("  host(2.1) vs plugin(2.0): %s\n",
                is_compatible(host_need, plugin_2_0) ? "兼容（拒绝加载则过严）" : "不兼容（minor 不足）");
    std::printf("  host(2.1) vs plugin(2.5): %s\n",
                is_compatible(host_need, plugin_2_5) ? "兼容" : "不兼容");
    std::printf("  host(2.1) vs plugin(3.0): %s\n",
                is_compatible(host_need, plugin_3_0) ? "兼容" : "不兼容（major 变，必须拒绝）");

    // 自检断言
    int failures = 0;
    const auto expect = [&](bool cond, const char* msg) {
        if (!cond) {
            ++failures;
            std::fprintf(stderr, "[FAIL] %s\n", msg);
        }
    };
    expect(offsetof(info_v1, api) == offsetof(info_v2_tail, api),
           "尾部追加必须保持 api 偏移不变");
    expect(offsetof(info_v1, kind) == offsetof(info_v2_tail, kind),
           "尾部追加必须保持 kind 偏移不变");
    expect(offsetof(info_v1, api) != offsetof(info_v2_mid, api),
           "头部插入改变了 api 偏移（二进制不兼容的来源）");
    expect(tail_read == 2, "老宿主读尾部追加版数据应得 api=2");
    expect(mid_read != 2, "老宿主读头部插入版数据应得错值（证明不兼容）");
    expect(is_compatible(host_need, plugin_2_5), "major 相同且 minor 够 → 兼容");
    expect(!is_compatible(host_need, plugin_3_0), "major 不同 → 二进制不兼容");

    if (failures == 0) {
        std::printf("\n[PASS] 全部断言通过\n");
        return 0;
    }
    std::fprintf(stderr, "\n[FAIL] %d 项断言失败\n", failures);
    return 1;
}
