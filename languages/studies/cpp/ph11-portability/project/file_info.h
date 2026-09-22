// file_info.h —— 文件信息与目录遍历接口（基于 std::filesystem，天然跨平台）
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace ftool {

struct FileInfo {
    std::uintmax_t size;      // 固定宽度类型：跨平台一致
    std::string modified;     // 修改时间（"YYYY-MM-DD HH:MM:SS"，UTC）
    bool is_dir;
};

// 读取文件大小与修改时间；路径不存在/不可读返回 nullopt（E.2：失败用返回值表达）
std::optional<FileInfo> file_info(const std::string& path);

// 列出目录条目（文件名，排序）；目录不存在/不可读返回 nullopt，空目录返回空 vector
std::optional<std::vector<std::string>> list_dir(const std::string& dir);

}  // namespace ftool
