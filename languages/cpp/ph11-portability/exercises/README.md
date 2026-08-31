# exercises —— 标准、编译器与可移植性阶段练习

完成顺序建议：按 1~5 顺序完成。参考实现在 `sol-*` 文件中，做完再看。验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`c++ -std=c++20 -Wall -Wextra`；本机无 GCC/MSVC，涉及这两家的条目如实标注「未在本环境验证」。练习 1~3 与 roadmap ph11「练习」小节的三个承诺一一对应，练习 4/5 覆盖 roadmap「学习内容」中的固定宽度类型与字节序。

## 练习 1：同一份代码双编译器编译，对齐告警（★）

- **目标**：同一份藏着两个常见笔误的代码，分别用 Apple clang 与 Homebrew clang 编译，记录两家告警，修复到双编译器零警告
- **要求**：
  - 写一段含 2 个笔误的代码：赋值当条件用（`if (x = 42)`）+ 链式比较（`if (a < b < 0)`）
  - 分别用 `c++` 与 `clang++` 编译（`-std=c++20 -Wall -c`），把两家的告警措辞记下来对照
  - 修复两处笔误，重编译确认两家都零警告
- **验收**：能说出修复前两处告警的措辞差异；修复后 `c++` 与 `clang++` 都零警告、运行输出符合预期
- **提示**：本机两家都是 clang，诊断措辞一致（实测 `-Wparentheses` / `-Wtautological-constant-compare`，链式比较在 clang 21 下甚至是 error）；若在真 GCC 上编译，告警命名会不同（如 `-Wbool-compare`）——GCC 侧未在本环境验证。告警对齐的核心是"同批代码三套编译器都过"，MSVC 用 `/W4 /WX`

## 练习 2：为平台 API 写适配层（★★）

- **目标**：仿 examples/ex05，把路径拼接 + 换行符两个平台差异收进适配层，接口头零平台宏
- **要求**：
  - 公共接口：`join_path(base, rel)` + `newline()`，头文件里**不允许出现任何平台宏**
  - 平台差异（路径分隔符 `/` vs `\`、换行符 `\n` vs `\r\n`）全部藏在实现里
  - 用 `-D_WIN32` 在本机编译验证 Windows 分支
- **验收**：POSIX 分支 `join_path("data","config.json")` 输出 `data/config.json`、`newline()` 打印 `0x0A`；`-D_WIN32` 分支输出 `data\config.json`、`0x0D 0x0A`；两个分支编译都零警告
- **提示**：**坑：能用 `std::filesystem`（C++17）就别手写路径**——适配层留给 filesystem 管不到的 API（socket、动态库、线程名等）；`newline()` 返回 `const char*`（F.20 返回指针而非输出参数）

## 练习 3：检查项目使用的 C++ 标准特性（★★）

- **目标**：写一个"标准特性探测器"，用 `__cplusplus`、`__has_include`、`__cpp_lib_*` 报告当前编译模式支持哪些特性，并对比 `-std=c++17` 与 `-std=c++20`
- **要求**：
  - 输出 `__cplusplus` 数值与对应的标准名（C++17/20/23）
  - 用 `__has_include` 探测 `<optional>`、`<format>` 是否存在（注意：只能在预处理指令里用，先转成宏常量）
  - 用 `__cpp_lib_filesystem` / `__cpp_lib_optional` / `__cpp_lib_format` 报告标准库特性（**必须先 include 对应头文件**）
  - 分别用 `-std=c++17` 与 `-std=c++20` 编译运行，对比两次输出的差异
- **验收**：能解释为什么 `__cpp_lib_*` 在两个 `-std` 下数值不同（或未定义）；能列出本机 libc++ 在 C++17 vs C++20 下至少 2 个特性宏差异
- **提示**：参考实现本机实测：`__cpp_lib_optional` 从 201606（C++17）升到 202106（C++20），`__cpp_lib_format` 从"未定义"变为 202110；`__has_include` 两个标准下都是 yes

## 练习 4：字节序无关的二进制序列化（★★）

- **目标**：实现 uint16/uint32 的"大端（网络序）"序列化与反序列化，不依赖平台字节序，round-trip 自测
- **要求**：
  - `put_u16be(v, out[2])` / `put_u32be(v, out[4])`：按"高位在前"写出字节
  - `get_u16be(in[2])` / `get_u32be(in[4])`：互逆读回
  - 运行期字节序探测：看 0x0102 首字节是 0x01（大端）还是 0x02（小端）
  - 自测：`0x01020304` 序列化后字节应为 `01 02 03 04`，读回等于原值
- **验收**：输出 `runtime endianness: little`（本机）；三个 round-trip 全部 `(OK)`；编译零警告
- **提示**：**坑：不要用 `reinterpret_cast` 直接把结构体当字节流**——结构体布局（padding/对齐）跨编译器不同，序列化必须逐字节手动拼；大端序正是网络协议（TCP/IP、HTTP 头长度字段）的约定

## 练习 5：跨平台二进制文件头（★★★ 综合题）

- **目标**：综合固定宽度类型 + 大端序列化 + 运行期字节序探测，实现一个跨平台二进制文件头（magic + version + 记录数 + 记录数组）的写读往返
- **要求**：
  - 布局固定：magic 4 字节 + version uint16 + count uint32 + 每条记录 uint64，全部大端
  - 全部用 `<cstdint>` 固定宽度类型，禁止裸 `int`/`long`
  - `serialize` / `deserialize` 互为逆操作，往返后字段逐一相等（退出码 0）
  - 用 `std::endian`（C++20 `<bit>`）打印本机字节序，验证"任何字节序机器读同一字节流结果一致"
- **验收**：输出 header 字节布局（magic `50 48 4C 31` + version `00 01` + count + 记录）、`readback ... (OK)`、退出码 0；编译零警告
- **提示**：参考实现把 `records[2] = {42, 43}` 写成 `... 2A ... 2B`（0x2A=42、0x2B=43，可对照验证）；给 `deserialize` 加"magic 不匹配就报错"是后续 ph12 生命周期/异常处理的自然扩展

> **提示**：参考实现仅作对照，先独立完成再复盘。sol-01 的修复前代码片段在题目里，sol 文件是修复后版本；sol-02 演示"适配层 + `-D_WIN32` 验证"的完整形态。进阶玩法（可选）：把练习 3 的探测器加 `__has_cpp_attribute` 探测；给练习 5 的文件头加 checksum 字段（参考 ph09 的 checksum 模块）。
