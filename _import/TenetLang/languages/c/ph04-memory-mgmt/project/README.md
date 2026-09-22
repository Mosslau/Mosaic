# 阶段项目：动态数组库（darray）

对应 roadmap ph04 推荐项目第一个「动态数组库」。用 `darray.h` + `darray.c` 多文件组织，附带 `main.c` 用 assert 做自测。

## 需求

实现一个泛化能力有限的动态数组库（本阶段只支持 `int`，指针化思路见「扩展方向」）：

- `darray_create()` / `darray_destroy()` —— 创建与销毁（释放全部内存）
- `darray_push()` —— 尾部追加，容量不够自动 2x 扩容；`realloc` 失败返回 -1 且**原数据不丢失**
- `darray_pop()` —— 弹出末尾元素（空数组返回 0 并置错误标记）
- `darray_get()` / `darray_set()` —— 按下标读写，越界返回 -1
- `darray_size()` / `darray_capacity()` —— 查询长度与容量
- 使用率 < 25% 时自动缩容（容量 > 16 才缩）

## 功能清单

| 功能 | 说明 |
|------|------|
| 2x 扩容 | 容量不足自动翻倍，`realloc` 失败路径不丢数据 |
| 缩容 | 使用率 < 25% 且容量 > 16 时容量减半 |
| 越界保护 | `get`/`set` 越界返回 -1，不写坏内存 |
| 空数组保护 | `pop` 空数组置错误标记，不越界 |
| 自测 | `main.c` 内 assert 覆盖扩容/缩容/越界/空数组四条路径 |

## 验收标准

- [ ] `gcc -Wall -Wextra -std=c99 darray.c main.c -o darray` 编译零警告
- [ ] 运行 `./darray` 全部 assert 通过（无输出即通过）
- [ ] 用 `valgrind --leak-check=full ./darray` 检查 `definitely lost` 为 0（本机无 valgrind 时改用 `-fsanitize=address`）
- [ ] 代码符合 ph04 内存管理要点：malloc 查 NULL、realloc 用临时指针、free 后置 NULL

## 扩展方向

- 用 `void *` + 元素大小参数泛化为任意类型（如 `darray_create(int elem_size)`）
- 支持 `darray_insert` / `darray_remove`（中间插入/删除）
- 把缩容策略改为显式 `darray_shrink_to_fit()` 调用

## 验证环境

- Apple clang 17（gcc 兼容），`-Wall -Wextra -std=c99`
- 编译：`gcc -Wall -Wextra -std=c99 darray.c main.c -o darray`
- 运行：`./darray`（assert 全过则无输出）
- 验证状态：已验证
