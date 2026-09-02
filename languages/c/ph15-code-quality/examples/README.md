# examples —— C 语言高级 C 与代码质量阶段完整示例

本目录是主文档第 6 章示例 1~6 的完整可运行版。**六个示例覆盖 roadmap ph15「学习内容」全部主题**：宏技巧与条件编译（ex01）、函数指针/回调与上下文约定（ex02）、表驱动状态机（ex03）、错误码设计（ex04）、日志系统与 trace id（ex05）、handle-based API/opaque pointer 与跨平台（ex06）。

验证环境（本机实测）：**Apple clang 21.0.0**（`cc`，macOS arm64，ProductVersion 26.6.2）。全部 C 代码 `cc -Wall -Wextra -std=c11` 零警告；产物一律写 `/tmp/ph15c-ex/`，仓库零残留。跨平台注意：ex05 的 `_WIN32` 分支、ex06 的平台探测宏中的 Windows 分支**未在本环境验证**（需 Windows），POSIX/macOS 分支全部实测。

## 一键构建与运行

```bash
make all      # 1. 构建并运行全部示例（输出即验证结果）
make ex01     # 2. 只跑某个（ex01 ~ ex06）
make clean    # 3. 清理 /tmp/ph15c-ex
```

## 示例清单

| 组 | 文件 | 覆盖主题 | 验证状态 |
|----|------|---------|----------|
| ex01 | `ex01-macro-tricks.c` | 宏技巧：副作用陷阱正反例（MAX 双求值 vs inline 函数）、do-while(0)、可变参宏（##__VA_ARGS__ 吞逗号）、X-Macro（枚举+字符串表同源）、条件编译（__STDC_VERSION__/平台宏） | 已验证：零警告，退出码 0；`MAX_BAD(i++,0)` 双求值 i 1→3 结果 2，`imax` 单求值 1→2 |
| ex02 | `ex02-callback-ctx.c` | 函数指针：typedef、传参、函数指针数组；回调 + void *ctx 上下文约定（谁注册谁负责 ctx 生命周期） | 已验证：零警告；回调顺序 A→timer→B 与各自 ctx 计数（1/2/3 次累计）实测一致 |
| ex03 | `ex03-state-machine.c` | 表驱动状态机：转移表 `(from, event) → (action, to)`、动作=函数指针、非法事件返回 -1 状态不变、状态序列自测 | 已验证：零警告；状态转移序列 `0122340` 实测，非法 DATA 在 CLOSED 被拒 |
| ex04 | `ex04-error-code.c` | 错误码设计：0 成功/负数错误、显式赋值 + 历史锁定注释（发布不改值、新增只追加）、错误详情出参（错误码+行号+原文快照）可追踪 | 已验证：零警告；-5/-3 两错误路径的行号与原文快照实测 |
| ex05 | `ex05-logging.c` | 日志系统：级别（DEBUG<INFO<WARN<ERROR）、阈值过滤、trace id、时间/文件:行诊断、LOG 宏自动带 __FILE__/__LINE__ | 已验证：零警告；阈值 DEBUG→WARN 过滤行为（emitted=6 dropped=2）与 trace=1a2b 行实测 |
| ex06 | `ex06-handle-api.c` | handle-based API/opaque pointer（衔接 ph14 的句柄心智到纯 C 库）、错误码契约、create/destroy/借用指针注释、条件编译平台探测 | 已验证：零警告；create→set/get→覆盖→destroy 全链路 + cfg_get 未找到键 rc=-3 实测；`_WIN32` 分支未在本环境验证 |

## 逐文件命令（可复现）

```bash
# ex01 宏技巧（副作用陷阱 / do-while(0) / 可变参宏 / X-Macro / 条件编译）
cc -Wall -Wextra -std=c11 ex01-macro-tricks.c -o /tmp/ph15c-ex/ex01 && /tmp/ph15c-ex/ex01

# ex02 函数指针与回调（上下文约定 + 回调顺序）
cc -Wall -Wextra -std=c11 ex02-callback-ctx.c -o /tmp/ph15c-ex/ex02 && /tmp/ph15c-ex/ex02

# ex03 表驱动状态机（转移序列实测）
cc -Wall -Wextra -std=c11 ex03-state-machine.c -o /tmp/ph15c-ex/ex03 && /tmp/ph15c-ex/ex03

# ex04 错误码设计（稳定、可追踪）
cc -Wall -Wextra -std=c11 ex04-error-code.c -o /tmp/ph15c-ex/ex04 && /tmp/ph15c-ex/ex04

# ex05 日志系统（级别过滤 / trace id / 诊断）
cc -Wall -Wextra -std=c11 ex05-logging.c -o /tmp/ph15c-ex/ex05 && /tmp/ph15c-ex/ex05

# ex06 handle-based API / opaque pointer（衔接 ph14）+ 跨平台探测
cc -Wall -Wextra -std=c11 ex06-handle-api.c -o /tmp/ph15c-ex/ex06 && /tmp/ph15c-ex/ex06
```

## 说明

- 主文档第 6 章内嵌片段摘自本目录文件（节选关键部分，完整文件以本目录为准），两者逐字一致。
- ex05 输出的时间列为运行时刻（随运行变化），其余行为输出（级别过滤条数、trace id、文件:行）均确定可复核；`__FILE__` 显示为编译时传入的路径（`ex05-logging.c`），行号随源码行位置变化。
- ex01 的 LOG 宏使用 GNU/Clang 的 `##__VA_ARGS__` 逗号吞并扩展（ISO C11 的 `...` 需至少一个实参；C23 提供标准化的 `__VA_OPT__(,)`），文档 3.1 有对照说明。
- 与 ph09 的边界：ph09 讲"平台差异怎么抽象"（条件编译做平台层），ph15 讲"宏/函数指针/状态机本身怎么写才不咬人"（ex01 的副作用陷阱即 ph15 视角）；ex05/ex06 的 Windows 分支与 ph09 同款标注——未在本环境验证。
