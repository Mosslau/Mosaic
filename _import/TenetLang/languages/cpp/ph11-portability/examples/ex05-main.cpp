// ex05-main.cpp —— 调用方只看到统一接口，不知道平台差异
#include "ex05-path.h"
#include <cstdio>

int main() {
    std::printf("%s\n", path::join("data", "config.json").c_str());
    std::printf("%s\n", path::join("data/", "config.json").c_str());
    std::printf("separator: %c\n", path::separator());
    return 0;
}
