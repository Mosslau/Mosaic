// ex01-stdint.cpp —— <cstdint> 固定宽度整数类型
// 主题：跨平台代码不能假设 int/long 的宽度，固定宽度类型把"恰好 N 位"变成编译期承诺。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex01-stdint.cpp -o /tmp/ex01-stdint
// 运行：    /tmp/ex01-stdint
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdint>   // 固定宽度类型 + INT32_MAX 等宏
#include <cstdio>

int main() {
    // 固定宽度：编译器保证"恰好"这么多位，任何平台都不打折
    std::printf("int8_t=%zu  int16_t=%zu  int32_t=%zu  int64_t=%zu\n",
                sizeof(int8_t), sizeof(int16_t), sizeof(int32_t), sizeof(int64_t));
    std::printf("uint8_t=%zu  uint16_t=%zu  uint32_t=%zu  uint64_t=%zu\n",
                sizeof(uint8_t), sizeof(uint16_t), sizeof(uint32_t), sizeof(uint64_t));

    // 边界值宏：来自 <cstdint>，与类型宽度联动
    std::printf("INT32_MAX=%d  UINT32_MAX=%u\n", INT32_MAX, UINT32_MAX);

    // "至少/最快"类型：宽度只保证下限，具体值由平台决定（教学：别假设具体宽度）
    std::printf("int_least8_t=%zu  int_fast32_t=%zu  intmax_t=%zu\n",
                sizeof(int_least8_t), sizeof(int_fast32_t), sizeof(intmax_t));

    // 反例：int/long 宽度跨平台不同（本机 macOS arm64 是 4/8，Windows 上是 4/4）
    std::printf("int=%zu  long=%zu  long long=%zu  void*=%zu\n",
                sizeof(int), sizeof(long), sizeof(long long), sizeof(void*));

    // 把"恰好 4 字节"变成编译期断言：写二进制格式时依赖的正是这条
    static_assert(sizeof(int32_t) == 4, "int32_t must be exactly 4 bytes");
    static_assert(sizeof(uint64_t) == 8, "uint64_t must be exactly 8 bytes");

    // 实际用途：二进制协议头/文件格式字段，长度固定、跨平台一致
    const uint32_t magic = 0x50484C31u;          // 'P''H''L''1'
    const uint16_t version = 1;
    std::printf("magic=0x%08X version=%u\n", magic, version);
    return 0;
}
