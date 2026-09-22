// file_sync.h —— 目录同步核心：递归扫描 + 差异比对 + 分块复制 + 校验
#ifndef PH09_FILESYNC_FILE_SYNC_H
#define PH09_FILESYNC_FILE_SYNC_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>

namespace filesync {

namespace fs = std::filesystem;

struct SyncStats {
    std::size_t scanned = 0;    // 扫描到的源文件数
    std::size_t copied = 0;     // 实际复制数
    std::size_t skipped = 0;    // 未变化跳过数
    std::size_t failed = 0;     // 失败数
    std::size_t copied_bytes = 0;
};

// 把 src 目录同步到 dst 目录（单向：src 为准，多出的 dst 文件不删除）
// 每个源文件：目标不存在或大小/修改时间不同 → 分块复制并校验；否则跳过
SyncStats sync_tree(const fs::path& src, const fs::path& dst,
                    std::string* err_out);

}  // namespace filesync

#endif  // PH09_FILESYNC_FILE_SYNC_H
