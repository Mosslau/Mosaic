// mystrlib.c —— ph14 示例 6 配套的自建 C 库（供 Rust 通过 extern "C" 调用）
// 编译：cc -Wall -Wextra -shared -fPIC -O2 -o /tmp/libmystrlib.dylib mystrlib.c
// 验证状态：已验证（Apple clang 21.0.0，macOS arm64；-Wall -Wextra 零警告；链接与运行见 ex06-ffi-c-library.rs 头部）
#include <stdint.h>

int32_t add_i32(int32_t a, int32_t b) { return a + b; }

uint64_t mul_u64(uint64_t a, uint64_t b) { return a * b; }

typedef struct {
    double x;
    double y;
} point2d_t;

double point_len(point2d_t p) { return __builtin_sqrt(p.x * p.x + p.y * p.y); }

const char *greet(void) { return "hello from C"; }
