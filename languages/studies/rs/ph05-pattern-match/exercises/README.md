# exercises —— 模式匹配与枚举阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。本阶段主题是「enum + match 让非法状态不可表达」：练习 1~3 对应 roadmap 承诺的三个练习（订单/设备状态建模、字符串状态码改 enum、match 处理消息），练习 4~5 进阶到 if let/while let/matches! 精简与状态机迁移。

## 练习 1：订单状态建模（★）

**目标**：用 `enum OrderState` 表达订单的五个状态，每个状态携带该状态特有的数据

**要求**：
- 变体：`Pending`（无数据）、`Confirmed { by: String }`（确认人）、`Shipped { tracking: String }`（快递单号）、`Delivered`、`Cancelled { reason: String }`
- 实现 `describe(&self) -> String`：match 覆盖全部变体，输出人类可读描述
- 实现 `is_final(&self) -> bool`：用 `matches!` 判断是否终态（Delivered / Cancelled）
- 派生 `Debug`、`Clone`、`PartialEq`

**验收**：编译零警告；`describe` 对五种状态分别输出不同描述；`is_final()` 对 Delivered、Cancelled 返回 `true`，对 Pending、Confirmed、Shipped 返回 `false`。

## 练习 2：设备状态：字符串状态码改 enum（★）

**目标**：把 `"online"` / `"offline"` / `"fault:500"` 这类字符串状态码改成 `enum DeviceStatus`，消除魔法字符串

**要求**：
- 变体：`Online`、`Offline`、`Fault(u32)`（携带错误码）
- 实现 `from_str(s: &str) -> Result<DeviceStatus, String>`：`"online"` / `"offline"` / `"fault:<数字>"` 合法，其余返回带原因的 `Err`
- 实现 `as_str(&self) -> String`：反向转回字符串（`Fault(code)` → `"fault:<code>"`）
- 转换边界用 `match` + 守卫处理，不裸 `unwrap`

**验收**：`from_str("online")` → `Ok(Online)`；`from_str("fault:500")` → `Ok(Fault(500))`；`from_str("disconnected")` → `Err(带原因)`；`Fault(500).as_str()` → `"fault:500"`；`as_str` 与 `from_str` 往返一致。

## 练习 3：match 处理不同消息类型（★★）

**目标**：用 `enum Message` 建模聊天消息的五种类型，用 match 穷尽分发处理

**要求**：
- 变体：`Text(String)`、`File { name: String, size: u64 }`、`Join { room: String }`、`Leave`、`Quit`
- 实现 `handle_message(&Message) -> String`：每种消息生成不同处理结果字符串（如文本原样转发、文件记录上传大小、加入房间、离开、退出）
- match 必须穷尽覆盖全部变体（不写 `_ =>`）
- 在 `main` 里构造包含全部五种消息的 `Vec`，逐条打印处理结果

**验收**：编译零警告；五种消息各输出一条不同前缀的结果；用 `matches!` 统计 `Text` 消息数并打印。

## 练习 4：if let / while let / matches! 精简（★★）

**目标**：在只关心部分情况时，用 `if let`、`while let`、`matches!` 替代完整 match

**要求**：
- 定义本地枚举 `Event { Write(String, i32), Delete(String), Expire(String) }`
- 遍历事件列表，用 `if let` 只处理 `Write`，其余变体静默跳过
- 再用一个完整 `match` 输出 `Delete` / `Expire` 的 key（对比 if let 与 match：一个只关心单分支、一个必须穷尽）
- 用 `while let` 从 `Vec<&str>` 栈中循环 `pop` 直到空
- 用 `matches!` 统计 `Write` 和 `Expire` 事件个数
- 用 `assert!` / `assert_eq!` 验证统计结果与栈空

**验收**：编译零警告；`if let` 分支只打印 Write 事件；`while let` 弹出全部元素且循环正常终止；Write/Expire 计数正确。

## 练习 5：订单状态机（★★★）

**目标**：给 `OrderState` 实现合法迁移表，非法迁移返回带原因的 `Err`

**要求**：
- 无数据变体：`Pending`、`Confirmed`、`Shipped`、`Delivered`、`Cancelled`
- 实现 `transition(&self, next: OrderState) -> Result<OrderState, String>`，合法迁移表：
  - `Pending → Confirmed | Cancelled`
  - `Confirmed → Shipped | Cancelled`
  - `Shipped → Delivered`
  - 其余组合一律 `Err`，错误消息说明"不允许从 X 迁移到 Y"
- 合法判定建议用 `matches!` + 或模式组合，禁止对合法迁移使用裸 `unwrap`
- 在 `main` 里演示一条完整链路（Pending → Confirmed → Shipped → Delivered）和至少两个非法迁移

**验收**：编译零警告；完整链路每步返回 `Ok`；`Delivered.transition(Cancelled)` 与 `Pending.transition(Delivered)` 均返回 `Err` 且错误消息含双方状态名。

> **提示**：练习 1/2/3 与主文档第 6 章示例 1/2/3 主题一致，但实现细节不同——先独立完成，再对照 `examples/` 中的示例查漏。`sol-*` 为参考实现（头注释已注明对应练习）。
