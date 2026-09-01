# ph14 阶段项目：受控缓冲区封装（SafeBuffer）

对应 roadmap ph14 推荐项目「受控缓冲区封装：提供安全 API，内部用少量 unsafe 操作切片」。在 unsafe 关键字 / 裸指针 / 安全抽象封装的基础上，落地为**对外零 unsafe、内部用 std::alloc + 裸指针管理原始内存**的完整程序，并内置「内存泄漏自检」验收。**纯 std、单文件**（`rustc` 直接编译，零第三方依赖）。

## 需求

一个可增长的字节缓冲区 `SafeBuffer`：

1. **安全 API 表面**：`new` / `write`（追加一段）/ `push_byte` / `as_slice` / `as_mut_slice` / `get`（越界 `None`）/ `len` / `capacity` / `clear` / `iter`——调用方不需要任何 `unsafe`。
2. **unsafe 内部**：原始分配用 `std::alloc`（`alloc`/`realloc`/`dealloc` + `Layout`），读写用裸指针与 `from_raw_parts`；不变量（`len ≤ cap`、`ptr` 指向 `cap` 字节分配、`[0, len)` 已初始化）由实现者维护，每处 unsafe 写 `// SAFETY:` 注释。
3. **内存不泄漏**：`Drop` 释放分配；程序内置全局分配计数器（`LIVE_ALLOCS`），结束时必须归零——自检式的泄漏验收。

## 功能清单

- [x] 倍增扩容（0→8→16→32→…，`next_power_of_two`），扩容后旧内容完整
- [x] 安全 API 全套 + 越界 `get` 返回 `None`（不 panic）
- [x] `as_mut_slice` 就地修改、`clear` 保留容量复用
- [x] `demo` 模式：断言 + 泄漏自检（`LIVE_ALLOCS == 0`）
- [x] `--stress N` 压力模式：N 字节逐字节 push 后全量校验 + 泄漏归零

## 构建与运行

```bash
# 1. 编译（产物输出 /tmp，仓库零二进制残留）
rustc --edition 2021 -D warnings src/main.rs -o /tmp/safebuf
# 2. 自包含验收（推荐先跑这个）
/tmp/safebuf
# 3. 压力路径（100 万字节）
/tmp/safebuf --stress 1000000
```

验证环境：rustc 1.92.0（macOS arm64），零第三方依赖。**已验证**。

## 实测输出

demo 模式（连跑 3 次输出一致）：

```text
1. 写入 17 字节（跨 3 次扩容 0→8→16→32），内容完整: len=17, cap=32
2. get 边界（get(17) 越界 = None）+ as_mut_slice 就地修改 OK
3. clear 保留容量，push_byte 复用 OK
4. iter 求和 = 3
5. 泄漏自检: drop 后 LIVE_ALLOCS = 0
demo 断言通过
```

压力模式（已实测 100 万字节）：

```text
stress: 1000000 字节 push 后逐一校验通过（cap = 1048576）
stress 断言通过（泄漏归零）
```

## 验收标准

- `rustc --edition 2021 -D warnings` 编译零警告（已验证）
- `demo`：全部断言通过、`LIVE_ALLOCS` 归零、退出码 0（已验证，连跑 3 次）
- `--stress 1000000`：1 000 000 字节逐字节 push 后逐一校验通过、泄漏归零（已验证）
- 调用方视角零 unsafe：对外 API 全部安全（代码中 `unsafe` 只出现在 `impl SafeBuffer` 内部）

## 扩展方向（可选）

- 用 `Layout::array::<T>` 泛型化（对标 `Vec<T>` 的极简版）——承接 ph19 内存布局、零拷贝与协议解析阶段（目录待建）
- 加 `into_raw_parts` / `from_raw_parts` 导出与重建（`Box::into_raw` 家族，衔接 ph10 智能指针阶段）
- 用 Miri（nightly）跑一遍全部路径——Miri 是 unsafe 代码的标准检查工具（本环境未装 nightly，未实测，如实标注）
- 多线程安全版本（`Mutex<SafeBuffer>` 或内部锁）——承接 ph12 并发与异步阶段
