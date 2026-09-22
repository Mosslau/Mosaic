# s03: Permission — 执行前的三道闸门

在 s02 的工具分发基础上，给每次工具调用插上三道权限闸门：

```
+-------+    +--------+    +--------+    +--------+    +------+
| Tool  | -> | Gate 1 | -> | Gate 2 | -> | Gate 3 | -> | Exec |
| call  |    | deny?  |    | match? |    | allow? |    |      |
+-------+    +--------+    +--------+    +--------+    +------+
     |            |             |             |
     v            v             v             v
  (normal)     (blocked)    (ask user)    (denied)
```

- **Gate 1 硬拒绝**：`rm -rf /`、`sudo`、`shutdown`、`reboot`、`mkfs`、`dd if=`、`> /dev/sda`。
  命中直接拦，不问用户（只作用于 bash）。
- **Gate 2 规则匹配**：文件工具路径逃逸 workspace；bash 含 `rm `、`> /etc/`、`chmod 777`。
  命中不直接拒，升级给 Gate 3。
- **Gate 3 用户确认**：暂停循环打印警告，读一行输入，`y`/`yes` 放行，其余（含 EOF）拒绝。

被拒的工具回填 `"Permission denied."` 作为 tool_result 给模型，模型看到后会自己调整策略。

## 相对 s02 的删改

权限系统不是纯新增，而是把 s02 散落在工具里的安全检查**上移**到统一管线：

| s02 的做法 | s03 的做法 |
|-----------|-----------|
| `run_bash` 内置 5 条黑名单，命中报 `Error:` | 上移到 Gate 1，扩到 7 条；`> /dev/` 收窄为 `> /dev/sda`，不再误伤 `> /dev/null` |
| 文件工具 `safe_path()` 硬拦越界（`Err`） | 上移到 Gate 2，越界改为询问用户，用户可放行 |

`agent_loop` 的实质改动只有一处：执行 handler 前先 `check_permission()`。

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s03_permission
```

试试让模型"把 /tmp/xxx 文件复制到 ../ 外面"，Gate 2/3 会拦下来问你。

可选环境变量同 s01：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **闸门独立成函数** | `check_deny_list` / `check_rules` / `ask_user` 各管一道，`check_permission` 只串联 |
| **stdin 依赖注入** | Gate 3 读输入走 `&mut impl BufRead` 参数，测试喂 `Cursor` 模拟键盘，不碰真 stdin |
| **判定纯函数化** | `decide()` 把"y/yes → 放行"的判定拆成纯函数，交互和逻辑分开测 |
| **默认拒绝** | EOF、读取失败、空输入一律视为拒绝——权限系统的安全默认值 |
| **词法路径解析** | `resolve_path` 不访问文件系统纯折叠 `..`，替代 s02 的 canonicalize（不存在文件不再报错；符号链接逃逸检测不到，教学可接受） |
| **SYSTEM 告知模型** | `"All destructive operations require user approval."` 让模型预期拒绝是正常流程 |

## 结构

```
s03_permission/
├── Cargo.toml          # 依赖与 s02 相同，无新增
├── README.md
└── src/
    └── main.rs         # 1261 行：s02 全套 + 权限管线（~260 行新增）
```

质量基线：`cargo build` 零错误、`cargo clippy` 零警告。

## 测试

```bash
cargo test -p s03_permission
```

37 个单元测试，覆盖：
- `truncate_lines` 截断边界、serde 契约模型（从 s01 携入）
- bash / read / write / edit / glob 工具 I/O（从 s02 携入）
- `resolve_path` 词法折叠 `..`、绝对路径优先
- Gate 1：7 条黑名单全命中、正常命令不误杀、只作用于 bash
- Gate 2：路径逃逸 / 破坏性关键词命中、正常操作放行、只读工具不参与
- Gate 3：`y`/`yes` 变体放行、其余拒绝、EOF 拒绝
- 管线集成：Gate 1 短路不询问、用户放行/拒绝、干净操作全通过

## 与 Python 版对比

对照 `../../python/s03_permission/code.py`（244 行）。三闸结构、拒绝文案、询问交互一一对应，差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 规则表 | dict + lambda 列表 | `match` 硬编码两条规则（教学场景更直白） |
| 用户输入 | `input()` 全局 stdin | `&mut impl BufRead` 注入，可单测 |
| 路径解析 | `Path.resolve()` 解析符号链接 | 词法折叠 `..`，不碰文件系统 |
| 判定函数 | `choice in ("y", "yes")` 内联 | `decide()` 独立纯函数 |
| 拒绝回填文案 | "Permission denied." | "Blocked by permission gate." | 避免模型误读为 OS 级拒绝后换等效命令绕过 |
| Gate2 破坏性关键词 | 3 个（rm / > /etc/ / chmod 777） | 4 个（+ `-delete`） | 防 find -delete 绕过，更严 |
| 越界文案 | read/write/edit 统一 "Writing outside workspace" | read 用 "Reading"、write/edit 用 "Writing" | 语义相同，措辞更精确 |
| 单元测试 | 无 | 36 个 |

## 后续章节

| 章节 | 主题 | 在 s03 基础上增加 |
|------|------|--------------------|
| s04 | Hooks | pre/post hook 挂载点 |
| s05 | TodoWrite | 计划工具 + reminder |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
