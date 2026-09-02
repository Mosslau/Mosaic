# ph15 阶段项目：fsm —— 通用状态机框架（表驱动）

> 对应 roadmap ph15「推荐项目」第一个「状态机框架」（第二个推荐项目「系统级日志库」本阶段未单独落地——ph09 项目已是完整的跨平台日志库，本阶段日志主题由 examples/ex05 演示级别/阈值过滤/trace id/诊断语义，避免与 ph09 重复造轮子）。一个可复用的表驱动 FSM 库 + 两个演示场景 + 自测，把本阶段「函数指针表驱动、稳定错误码、opaque 句柄、可测试 API、零全局状态」全部落地成可运行代码，roadmap 必会概念"状态机适合解析器、任务调度、连接管理和存储恢复流程"由场景 A（连接管理）与场景 B（数据包解析）实证。

## 需求

实现一个通用状态机框架库 `fsm.h` / `fsm.c`：

- **转移表驱动**：状态机行为完全由一张只读表描述——每行 `(from_state, event, action, to_state)`；增删状态/事件只改表，框架代码不动
- **动作是函数指针**：`fsm_action_fn(ctx, from, event, to)`，动作收 ctx（衔接 ph15 回调上下文约定）；动作可缺省（NULL）
- **稳定错误码**：0 成功、负数错误（`FSM_ERR_BADARG=-1` / `FSM_ERR_ILLEGAL=-2` / `FSM_ERR_NOMEM=-3` / `FSM_ERR_FULL=-4`），不用 errno；非法事件返回错误码且状态不变
- **opaque 句柄 + 零全局状态**：struct 定义藏在 fsm.c，头文件只见 `fsm_t`；状态全在句柄内，可同时开多个互不干扰的实例
- **可测试 API（诊断）**：每次合法转移记录进轨迹缓冲，`fsm_trace_len` / `fsm_trace` 可读回完整转移序列——自测不必靠 stdout 匹配
- **命令行演示**：`fsm-demo` 跑两个场景 + 错误路径自测（断言 + 退出码即结果）

## 功能清单

- [x] `fsm_new(table, ntrans, init_state, ctx, err_out)`：拷贝转移表进句柄；坏参数返回错误码
- [x] `fsm_fire(f, event)`：查表执行动作并换状态，返回新状态；非法事件返回 `FSM_ERR_ILLEGAL` 状态不变
- [x] `fsm_state` / `fsm_destroy` / `fsm_strerror`：查询与生命周期（谁 new 谁 destroy）
- [x] `fsm_trace_len` / `fsm_trace`：轨迹读回（最近 64 条，满后转移照常执行仅不再记录——诊断不中断语义）
- [x] 场景 A：连接管理状态机（含 DATA 自环、CLOSED 下非法 DATA 被拒）
- [x] 场景 B：数据包解析状态机（动作全 NULL，证明动作可缺省）
- [x] 错误路径：空句柄 fire / 空表 create
- [x] Makefile：`make`（构建）/ `make test`（自测）/ `make clean`

## 验收标准

- [x] `make` 零警告（`-Wall -Wextra -std=c11`，Apple clang 21.0.0 实测）
- [x] `make test` 全部断言通过、退出码 0（实测 20 项 PASS：A 场景 12 项 + B 场景 5 项 + 错误路径 3 项，见下）
- [x] 非法事件返回错误码且状态不变、轨迹只记录合法转移（实测：CLOSED 下 DATA 被拒后状态仍 CLOSED，轨迹 6 条 = 6 次合法转移）
- [x] `make clean` 零残留（产物全部在 /tmp/ph15c-proj，仓库内无 .o / 可执行文件 / .dSYM）

## 验证

```bash
make            # 1. 构建（-Wall -Wextra -std=c11, 零警告）
make test       # 2. 自测（20 项 PASS 退出码 0）
make clean      # 3. 清理 /tmp/ph15c-proj
```

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64），C11。`make test` 实测输出摘要：

```text
=== ph15 project: 通用状态机框架 ===
场景 A: 连接状态机
PASS: A: 创建成功 … PASS: A: 轨迹[0] = CLOSED--CONNECT-->LISTEN   (12 项)
场景 B: 数据包解析状态机(动作缺省)
PASS: B: 创建成功(动作全 NULL 也合法) … PASS: B: DONE 后 HEADER 被拒  (5 项)
错误路径: 坏参数
PASS: badarg: 空句柄 fire / 空表被拒                               (3 项)
project: 全部断言通过, 退出码 0
```

## 扩展方向

- 查表改索引：大规模状态机用 (from, event) 直接索引（稀疏表 → 哈希），`fsm_fire` 从 O(n) 到 O(1)——roadmap §15 练习「通用状态机框架」的进阶
- 动作返回下一状态替代表中 to_state（表驱动变代码驱动，适合状态转移需动态计算的场景）
- 轨迹加时间戳/事件名，接 examples/ex05 的 trace id 思路做成诊断工具
- 用本项目框架重写 ph13/ph16 的解析场景（WAL replay 的状态机版）——roadmap 必会概念"状态机适合存储恢复流程"的落地预演
