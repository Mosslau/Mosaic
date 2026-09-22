# examples —— 内存管理阶段完整示例

验证环境：Apple clang 17（gcc 兼容），编译命令统一 `gcc -Wall -Wextra -std=c99`。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-dyn-array.c` | 动态数组：2x 扩容 + 使用率 <25% 缩容，realloc 失败不丢数据 | `gcc -Wall -Wextra -std=c99 ex01-dyn-array.c -o ex01-dyn-array` | `./ex01-dyn-array` |
| `ex02-dyn-str.c` | 动态字符串：append 自动扩容，处理 `\0` 结尾 | `gcc -Wall -Wextra -std=c99 ex02-dyn-str.c -o ex02-dyn-str` | `./ex02-dyn-str` |
| `ex03-mem-pool.c` | 固定块内存池：空闲链表 O(1) 分配/释放，池空返回 NULL | `gcc -Wall -Wextra -std=c99 ex03-mem-pool.c -o ex03-mem-pool` | `./ex03-mem-pool` |

三个示例均已在 Apple clang 17（gcc 兼容）下编译零警告并运行验证（已验证）。
