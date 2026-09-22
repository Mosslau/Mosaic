# exercises —— 内存管理阶段练习

完成顺序建议：先独立完成 1~3 题，再完成第 4 题（工具链实践）。参考实现在 `sol-*` 文件中，做完再看。

## 练习 1：动态数组（push/pop/扩容/缩容）

- **目标**：实现一个 `DynArray`（`int` 元素），支持 `push`、`pop`、自动 2x 扩容、使用率 <25% 时缩容
- **要求**：
  - `da_push` 扩容失败时返回 -1 且**原数据不丢失**（用临时指针接 `realloc` 返回值）
  - `da_pop` 返回被弹出的值，数组为空时返回 0 并置错误标记
  - 用 `-Wall -Wextra` 编译零警告
- **验收**：插入 20 个元素后 cap 为 32；弹出到 4 个后 cap 缩为 16；`free` 后无泄漏

## 练习 2：动态字符串（DynStr）

- **目标**：实现 `DynStr`，支持 `append`、`assign`（整体赋值）、`clear`（清空）
- **要求**：
  - 内部始终以 `\0` 结尾，`len` 不含 `\0`
  - 扩容按 2x 增长，`append` 失败返回 -1
  - `clear` 只清内容不缩容（避免频繁 realloc）
- **验收**：`append("Hello") + append(", ") + append("World!")` 得到 `"Hello, World!"`，len=13

## 练习 3：简单固定块内存池

- **目标**：实现 64 字节固定块内存池，`pool_alloc`/`pool_free` 均为 O(1)
- **要求**：
  - 一次申请 16 个 slot，用空闲链表管理
  - `pool_alloc` 池满返回 NULL
  - `pool_free` 通过 `offsetof(Block, data)` 反推块头
- **验收**：循环分配 16 块全成功、第 17 块返回 NULL；释放后再分配成功；`free(chunk)` 整体释放

## 练习 4：用 ASan 检查内存问题

- **目标**：体验 `-fsanitize=address` 定位越界访问
- **要求**：
  - 写一段**故意越界**的程序：`int a[4]; a[4] = 0;`（数组下标越界）
  - 用 `gcc -fsanitize=address -g -Wall -Wextra -std=c99` 编译运行
  - 在 ASan 输出中找到报错的源码行号，确认错误类型为 heap-buffer-overflow 或 stack-buffer-overflow
- **验收**：能说出 ASan 报告里三件事——错误类型、越界地址、源码位置
- **注意**：`sol-04-buggy-bounds.c` 是故意出错示例，**必须**用 `-fsanitize=address` 编译运行，否则行为未定义；本仓库验证环境编译通过，但沙箱限制 ASan 二进制运行，报错输出请在本机验证
