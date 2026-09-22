// path_util.h —— 平台适配层公共接口：零平台宏，平台差异全部藏在实现里
#pragma once

#include <string>

namespace ftool {

// 路径工具：跨平台统一语义，实现按平台（POSIX/Windows）分流
char separator();                          // 平台路径分隔符（'/' 或 '\\'）
std::string join(const std::string& base, const std::string& rel);   // 拼接路径
std::string normalize(const std::string& path);                      // 去重复分隔符、去结尾分隔符
std::string extension(const std::string& path);                      // 扩展名（含点，无则空串）

}  // namespace ftool
