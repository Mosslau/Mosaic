// mini_lsm.cpp —— Mini LSM KV：CLI 演示 + 自测套件
// ph22 project：把 WAL + MemTable（复用 ph21 skip_list）+ SSTable（含 Bloom）串成一台
// 可重启恢复的 mini KV。本文件驱动验收标准对应的四组自测：
//   [1] 基础语义：put/del/get/scan
//   [2] WAL replay 恢复 + 残尾容忍修复（“重启后 WAL replay 恢复”）
//   [3] 手动 flush 多层 + tombstone 跨层遮挡 + 重启后 range scan 与基准一致
//   [4] 自动 flush 多 SSTable + bloom 拦截统计 + 全量恢复
// 数据目录一律在 /tmp/ph22-proj-*，运行结束由 make clean 清理（仓库不落任何文件）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）+ Homebrew clang 21.1.8；
// 命令（等价 Makefile 目标）：
//   clang++ -std=c++20 -Wall -Wextra -I. mini_lsm.cpp -o /tmp/ph22-project-minilsm && /tmp/ph22-project-minilsm
// 验证状态：已验证（双编译器零警告、断言全绿、退出码 0）

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>

#include "lsm.h"

// —— 测试框架 ——
static int g_failed = 0;
static int g_checks = 0;

#define CHECK(cond)                                                        \
    do {                                                                   \
        ++g_checks;                                                        \
        if (!(cond)) {                                                     \
            std::cerr << "FAIL: " << #cond << " (line " << __LINE__ << ")\n"; \
            ++g_failed;                                                    \
        }                                                                  \
    } while (0)

// 递归删除临时目录（文件 + 目录本身）
static void rm_dir(const std::string& path) {
    DIR* d = ::opendir(path.c_str());
    if (!d) {
        return;
    }
    while (dirent* e = ::readdir(d)) {
        const std::string name = e->d_name;
        if (name == "." || name == "..") {
            continue;
        }
        const std::string full = path + "/" + name;
        ::unlink(full.c_str());
    }
    ::closedir(d);
    ::rmdir(path.c_str());
}

static std::string join(const std::vector<std::pair<std::string, std::string>>& rows) {
    std::string out;
    for (const auto& [k, v] : rows) {
        if (!out.empty()) {
            out += ' ';
        }
        out += k + "=" + v;
    }
    return out;
}

int main() {
    // ============ [1] 基础语义（纯内存 + WAL，不 flush） ============
    {
        const std::string dir = "/tmp/ph22-proj-d1";
        rm_dir(dir);
        minilsm::kvdb db{dir, 0};  // flush_bytes=0：关闭自动 flush
        db.put("alpha", "1");
        db.put("beta", "2");
        db.put("beta", "22");   // 覆盖
        db.del("alpha");        // 删除 = tombstone 写入
        CHECK(db.get("alpha") == std::nullopt);
        CHECK(db.get("beta") == std::string("22"));
        CHECK(db.mem_size() == 2);  // beta + alpha 的 tombstone（删除也是写入，不 erase 节点）
        const auto all = db.range_scan("", "");
        std::cout << "[1] 基础语义: scan = " << join(all) << '\n';
        CHECK(all.size() == 1 && all[0].first == "beta" && all[0].second == "22");
        rm_dir(dir);
    }

    // ============ [2] WAL replay 恢复 + 残尾容忍 ============
    {
        const std::string dir = "/tmp/ph22-proj-d2";
        rm_dir(dir);
        {
            minilsm::kvdb db{dir, 0};
            for (int i = 1; i <= 5; ++i) {
                db.put("k" + std::to_string(i), "v" + std::to_string(i));
            }
        }  // 进程结束 = 模拟崩溃（没有 close 清理）
        // 再在 WAL 尾部塞 5 字节残尾，模拟“崩溃时最后一条写了一半”
        {
            const std::string walp = dir + "/mini.wal";
            const int fd = ::open(walp.c_str(), O_WRONLY | O_APPEND);
            CHECK(fd >= 0);
            const char junk[5] = {'x', 'y', 'z', 'a', 'b'};
            CHECK(::write(fd, junk, sizeof(junk)) == static_cast<ssize_t>(sizeof(junk)));
            ::close(fd);
        }
        minilsm::kvdb db{dir, 0};  // reopen：replay + 残尾修复
        std::size_t found = 0;
        for (int i = 1; i <= 5; ++i) {
            const auto v = db.get("k" + std::to_string(i));
            if (v == std::string("v" + std::to_string(i))) {
                ++found;
            }
        }
        db.put("k6", "v6");  // 修复后日志可继续追加
        std::cout << "[2] WAL replay 恢复: 5/5 命中, k6="
                  << (db.get("k6") == std::string("v6") ? "v6" : "?") << '\n';
        CHECK(found == 5);
        CHECK(db.get("k6") == std::string("v6"));
        rm_dir(dir);
    }

    // ============ [3] 手动 flush：多层 + tombstone 跨层 + 重启一致性 ============
    {
        const std::string dir = "/tmp/ph22-proj-d3";
        rm_dir(dir);
        {
            minilsm::kvdb db{dir, 0};
            // 批次 A → SSTable 1
            for (int i = 1; i <= 9; ++i) {
                db.put("k0" + std::to_string(i), "va");
            }
            db.flush();
            // 批次 B（覆盖 2 个 + 删除 1 个）→ SSTable 2
            db.put("k02", "vb");
            db.put("k03", "vb");
            db.del("k05");
            db.flush();
            // 批次 C 留在内存（WAL 记录，不 flush）
            db.put("k10", "vc");
            CHECK(db.sstable_count() == 2);
        }
        // 重启：2 个 SSTable + WAL replay(k10)
        minilsm::kvdb db{dir, 0};
        CHECK(db.sstable_count() == 2);
        CHECK(db.get("k01") == std::string("va"));
        CHECK(db.get("k02") == std::string("vb"));   // 新 SSTable 覆盖旧的 va
        CHECK(db.get("k03") == std::string("vb"));
        CHECK(db.get("k05") == std::nullopt);        // tombstone 跨层遮挡 SSTable1 的 va
        CHECK(db.get("k10") == std::string("vc"));   // WAL replay 回到内存
        CHECK(db.get("k99") == std::nullopt);

        // range scan 跨 MemTable + SSTable1 + SSTable2 与基准一致
        const auto scan = db.range_scan("", "");
        std::vector<std::pair<std::string, std::string>> ground{
            {"k01", "va"}, {"k02", "vb"}, {"k03", "vb"}, {"k04", "va"}, {"k06", "va"},
            {"k07", "va"}, {"k08", "va"}, {"k09", "va"}, {"k10", "vc"},
        };
        std::cout << "[3] 重启后全表 scan: " << join(scan) << '\n';
        CHECK(scan == ground);
        const auto part = db.range_scan("k04", "k08");
        CHECK(part.size() == 3 && part[0].first == "k04" && part[0].second == "va" &&
              part[2].first == "k07");  // [k04, k08)：k04 k06 k07（k05 被删）
        rm_dir(dir);
    }

    // ============ [4] 自动 flush + bloom 拦截 + 全量恢复 ============
    {
        const std::string dir = "/tmp/ph22-proj-d4";
        rm_dir(dir);
        {
            minilsm::kvdb db{dir, 350};  // 阈值 350 字节：40 个 put 应触发 ≥2 次自动 flush
            for (int i = 0; i < 40; ++i) {
                char k[16], v[16];
                std::snprintf(k, sizeof(k), "k%02d", i);
                std::snprintf(v, sizeof(v), "val-%02d", i);
                db.put(k, v);
            }
            CHECK(db.sstable_count() >= 2);  // 自动 flush 确实发生多次
            CHECK(db.get("k07") == std::string("val-07"));

            // 大量“不存在”点查 → bloom 拦截计数应增长（逐 sstable 计数，聚合）
            const std::size_t before = db.bloom_negatives_total();
            for (int i = 0; i < 300; ++i) {
                char q[16];
                std::snprintf(q, sizeof(q), "zz%03d", i);
                CHECK(db.get(q) == std::nullopt);
            }
            const std::size_t after = db.bloom_negatives_total();
            std::cout << "[4] 自动 flush: sstable=" << db.sstable_count()
                      << ", bloom 拦截计数 " << before << " -> " << after << '\n';
            CHECK(after > before);
        }
        // 重启：全量 40 个 key 仍在（SSTable 恢复，无 WAL）
        minilsm::kvdb db{dir, 0};
        std::size_t ok = 0;
        for (int i = 0; i < 40; ++i) {
            char k[16], v[16];
            std::snprintf(k, sizeof(k), "k%02d", i);
            std::snprintf(v, sizeof(v), "val-%02d", i);
            if (db.get(k) == std::string(v)) {
                ++ok;
            }
        }
        const auto all = db.range_scan("", "");
        std::cout << "[4] 重启后恢复 " << ok << "/40, scan 条数 " << all.size() << '\n';
        CHECK(ok == 40);
        CHECK(all.size() == 40);
        rm_dir(dir);
    }

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-project-minilsm OK\n";
        return 0;
    }
    return 1;
}
