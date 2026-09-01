# exercises —— Unsafe Rust 与安全抽象阶段练习

完成顺序建议：按 1~4 顺序完成，对应主文档第 3 章 3.1~3.5 与第 6 章示例的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。全部为单文件、零第三方依赖，统一用 `rustc --edition 2021 -D warnings` 单文件编译（产物输出 `/tmp/`）。

> 练习 1~3 围绕「最小 unsafe 边界」：unsafe 只出现在函数/结构体内部，对外 API 全部安全。
> 练习 4 是 FFI 调用基础（libc）。卡壳时先回读主文档 3.x 对应小节，最后再看 `sol-*`。

## 练习 1：把 unsafe 块包在安全函数内（★）

- **目标**：用裸指针 + 指针运算实现三个**安全函数**（对应 roadmap 练习「把 unsafe 块包在安全函数内」）
- **要求**：
  - `sum_raw(ptr: *const i32, len: usize) -> i32`：裸指针遍历求和（用 `ptr.add(i)`，不用索引/迭代器）
  - `max_raw(ptr: *const i32, len: usize) -> i32`：求最大值；空输入直接 `assert!`（安全 API 不默默返回垃圾值）
  - `first_byte(ptr: *const i32) -> u8`：把指针 `as *const u8` 后取首字节
  - unsafe 块只包「解引用/运算」单条语句（最小 unsafe 边界），调用方视角完全安全
- **验收**：`rustc --edition 2021 -D warnings sol-01-raw-pointer-safety.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出含 `sum_raw = 150`、`max_raw = 50`、`first_byte(10) = 10`、`断言通过`

## 练习 2：unsafe fn 契约 + 边界测试（★★）

- **目标**：手写 `get_unchecked` 并写出 `# Safety` 契约，再写安全包装强制契约（对应 roadmap 练习「阅读标准库中的 unsafe 封装示例」与「为 unsafe 抽象写边界测试」）
- **要求**：
  - `unsafe fn get_unchecked(slice: &[u8], idx: usize) -> u8`：内部用 `slice.get_unchecked(idx)`，doc 注释写明 `# Safety`（idx 必须 < len）
  - `fn get_checked(slice: &[u8], idx: usize) -> Option<u8>`：安全侧检查边界后调用 unsafe 路径
  - 边界测试至少 5 组：首元素/末元素/越界/空切片/空切片越界
- **验收**：`rustc --edition 2021 -D warnings sol-02-unsafe-fn-contract.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出含 `1. get_checked 边界测试 5 组全部通过`、`2. unsafe 路径 get_unchecked(data, 2) = 30`、`断言通过`

## 练习 3：最小安全抽象 MiniVec（★★★）

- **目标**：用 `std::alloc`（`alloc`/`realloc`/`dealloc` + `Layout`）手写 `MiniVec`（i32 版），对外只有安全 API（对应 roadmap 推荐项目「受控缓冲区封装」的迷你版）
- **要求**：
  - 字段 `ptr: NonNull<i32>` + `len` + `cap`；不变量：`len ≤ cap`、`ptr` 按 `cap` 分配（`cap == 0` 时用 `NonNull::dangling()` 占位）
  - 安全 API：`new` / `push`（满则倍增扩容 0→4→8→16→…）/ `get`（越界 `None`）/ `len` / `capacity` / `as_slice` / `pop`
  - `impl Drop` 释放分配（忘记释放就是泄漏——扩容后旧内存也由 realloc 管理）
  - 每处 unsafe 写 `// SAFETY:` 注释说明不变量如何保证
- **验收**：`rustc --edition 2021 -D warnings sol-03-mini-vec.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出含 `len=17, cap=32, 扩容后内容完整`、`get(17) 越界 = None`、`pop() = Some(16), len = 16`、`断言通过`

## 练习 4：FFI 调用 libc（★★）

- **目标**：用 `extern "C"` 声明并调用 libc 的 `strlen` / `abs` / `malloc` / `free`（对应 roadmap 学习内容「FFI 调用基础」；调自建 C 库见 examples/ex06）
- **要求**：
  - `strlen` 接收 `*const c_char`，用 `CString::new(...).unwrap()` 构造 C 字符串（自行计算并断言 UTF-8 字节数）
  - `malloc(8)` 后用 `from_raw_parts_mut` 包装成切片写入 `1..=8` 并求和，最后 `free`
  - 每处调用都在 unsafe 块内（E0133 复习），注释说明「谁分配谁释放」
- **验收**：`rustc --edition 2021 -D warnings sol-04-ffi-libc.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；输出含 `strlen("练习 FFI") = 10`、`abs(-7) = 7`、`malloc 8 字节写入 1..=8, sum = 36`、`断言通过`

> **提示**：练习 1~2 练「最小 unsafe 边界」，练习 3 练「安全抽象封装」，练习 4 练「FFI 基础」——四题做完即覆盖 roadmap 全部必会概念（unsafe 不关闭借用检查见 examples/ex04，UB 行为差异见 examples/ex03）。
