// project/main.cpp —— RAII 文件类（演示入口 + 断言式测试）
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp wal_file.cpp -o wal_file
// 运行：./wal_file
// 已验证：本环境编译零警告，全部断言通过
#include <cassert>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>

#include "wal_file.h"

int main() {
    const char* path = "/tmp/ph03_project_wal.log";
    std::remove(path);                             // 清理旧文件

    // 1. 基本追加 + flush + 离开作用域自动关闭
    {
        WalFile wal(path);
        assert(wal);                               // 打开成功
        assert(wal.append("key1", "value1"));
        assert(wal.append("key2", "value2"));
        assert(wal.flush());
    }  // 析构自动 fclose

    // 2. 移动语义：移动后源对象失效，目标持有句柄
    {
        WalFile wal(path);
        WalFile moved = std::move(wal);            // 移动构造
        assert(!wal);                              // 源对象失效
        assert(moved);                             // 目标持有句柄
        assert(moved.append("key3", "value3"));
    }

    // 3. 回读验证：内容与写入顺序一致
    std::FILE* f = std::fopen(path, "r");
    assert(f != nullptr);
    char line[256];
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "key1\tvalue1\n") == 0);
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "key2\tvalue2\n") == 0);
    assert(std::fgets(line, sizeof(line), f) != nullptr);
    assert(std::strcmp(line, "key3\tvalue3\n") == 0);
    std::fclose(f);
    std::remove(path);

    std::cout << "全部断言通过\n";
    return 0;
}
