// checksum.h —— FNV-1a 校验和（文件同步工具用）
#ifndef PH09_FILESYNC_CHECKSUM_H
#define PH09_FILESYNC_CHECKSUM_H

#include <cstddef>
#include <cstdint>
#include <string>

namespace filesync {

// FNV-1a 滚动校验：state 跨块累积；初值 fnv1a(nullptr, 0)
std::uint32_t fnv1a(const char* buf, std::size_t n,
                    std::uint32_t state = 2166136261u);

// 计算整文件校验和；打开失败返回 false
bool file_checksum(const std::string& path, std::uint32_t* sum_out);

}  // namespace filesync

#endif  // PH09_FILESYNC_CHECKSUM_H
