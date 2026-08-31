// ex05-path.h —— 平台适配层：对外只暴露统一接口，平台差异全部藏在实现里
#pragma once
#include <string>

namespace path {
    char separator();
    std::string join(const std::string& base, const std::string& rel);
}
