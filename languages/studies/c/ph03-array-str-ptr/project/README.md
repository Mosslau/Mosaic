# ph03 阶段项目：字符串处理库

## 需求

对应 Roadmap「ph03 数组、字符串、指针阶段」推荐项目之一。实现一个不依赖标准库 `<string.h>` 的字符串处理库：`my_strlen`、`my_strcpy`、`my_strcmp`、`my_strcat`、`my_strstr`。采用多文件组织：`mystr.h`（声明 + include guard）、`mystr.c`（实现）、`main.c`（演示入口 + 断言式测试）。

## 功能清单

- [ ] `my_strlen`：指针遍历求长度，不含 `\0`
- [ ] `my_strcpy`：复制含 `\0`，返回目标指针
- [ ] `my_strcmp`：字典序比较，用 `unsigned char` 比较避免符号问题
- [ ] `my_strcat`：追加到目标末尾，覆盖目标 `\0`
- [ ] `my_strstr`：朴素匹配找子串，找不到返回 `NULL`，空子串返回原串
- [ ] 头文件 include guard 防重复包含

## 验收标准

- `gcc -Wall -Wextra -std=c99 main.c mystr.c -o mystr` 编译零警告
- `my_strlen("hello")` = 5；`my_strcmp("abc","abd")` < 0
- `my_strcat` 后能正确打印拼接结果；`my_strstr("hello world","world")` 返回偏移 6
- 全程不调用 `<string.h>` 的 `strlen/strcpy/strcmp/strcat/strstr`

## 扩展方向（可选）

- 用断言（`assert`）把演示输出改成单元测试 —— 属于 ph11 测试阶段
- 加 `my_strncpy`/`my_strncat` 安全版本 —— 涉及边界长度参数，属 ph04 内存管理阶段

## 验证环境

Apple clang 17.0.0（gcc 兼容），标准 C99。编译：`gcc -Wall -Wextra -std=c99 main.c mystr.c -o mystr`；运行：`./mystr`。已在本环境验证。
