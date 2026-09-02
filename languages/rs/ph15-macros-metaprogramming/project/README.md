# ph15 阶段项目：事件结构体宏（event-hub）

对应 roadmap ph15 推荐项目「事件结构体宏：为多类事件生成统一打印、校验或序列化辅助代码」。在主文档 macro_rules! / derive 宏的基础上，落地为一个**声明宏（define_events!）+ 两类 derive（serde / thiserror）协作**的 cargo 工程（lib + bin）：

- **`define_events!`（声明宏，库的入口）**：一次定义多类事件结构体，自动 derive `Debug/Clone/PartialEq/Serialize/Deserialize`（derive 属性写在宏展开体里），并为每个结构体生成 `impl Event`——`kind()` 种类标签 + `render()` 统一打印。`#[macro_export]` 导出 + `$crate::Event` 路径，宏可在**别的 crate**（本项目的 main 二进制）里使用。
- **serde derive**：`HubEvent` 枚举用 `#[serde(tag = "kind")]` **内部标签**序列化——JSON 自带 `"kind": "login"` 判别字段，与宏生成的 `kind()` 字符串一一对应（「宏生成标签」与「derive 生成标签」两种机制的同一来源）。
- **thiserror derive**：事件 JSON 解析错误建模为 `HubError`（`#[from] serde_json::Error` 自动生成 From，`?`/`HubError::from` 直接转换）。

## 需求

1. 声明宏 `define_events!` 批量生成事件结构体与统一辅助代码（打印 + 标签）。
2. 事件支持 serde 序列化/反序列化（内部标签 JSON）。
3. 解析错误用 thiserror 建模；demo 自包含验收（断言全绿）。

## 功能清单

- [x] `define_events!`：预置三类事件（Login / OrderPlaced / PaymentFailed），main 里再定义第四类（DownloadFinished）证明跨 crate 可用
- [x] 统一打印：`render()` 输出 `[kind] field=value ...`（字段顺序 = 结构体声明顺序，实测确定性可断言）
- [x] 统一序列化：`HubEvent` 内部标签 JSON；反序列化往返一致
- [x] 错误建模：未知 `kind` 的 JSON → serde 错误 → `HubError::Json`（thiserror Display 实测）
- [x] demo：5 段断言全部通过

## 构建与运行

```bash
# 1. 配置国内镜像（一次即可，内容见 examples/README）；构建（target 输出 /tmp，仓库零二进制残留）
cd project
CARGO_TARGET_DIR=/tmp/ph15-project-target cargo run
# 2. 严格零警告复查（可选）
CARGO_TARGET_DIR=/tmp/ph15-project-target RUSTFLAGS="-D warnings" cargo build
```

验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20（rsproxy 拉取，Cargo.lock 锁定）。**已验证**。

## 实测输出

```text
== 1. 统一打印（define_events! 生成 render()）==
  [login] user="ada" ok=true
  [order_placed] order_id=9001 amount=2
  [payment_failed] order_id=9001 reason="insufficient_funds"
  [download_finished] file="/tmp/rust.tar.gz" bytes=12345
== 2. 统一序列化（HubEvent 内部标签 kind）==
  1. {"kind":"login","user":"ada","ok":true}
  2. {"kind":"order_placed","order_id":9001,"amount":2}
  3. {"kind":"payment_failed","order_id":9001,"reason":"insufficient_funds"}
== 3. 反序列化往返 ==
  round-trip 一致 = true
== 4. 未知 kind 报错（thiserror derive 错误类型）==
  事件 JSON 解析失败: unknown variant `nuke`, expected one of `login`, `order_placed`, `payment_failed` at line 1 column 14
== 5. HubEvent 分发打印 ==
  [order_placed] order_id=9001 amount=2

demo 断言全部通过
```

## 验收标准

- `cargo build` 编译零警告（已验证，含 `RUSTFLAGS="-D warnings"` 复查）
- `cargo run` demo：5 段断言全部通过、退出码 0（已验证，连跑 3 次输出一致）
- 宏生成的事件结构体序列化/反序列化正确（内部标签 `kind` 与宏的 `kind()` 标签一致，断言覆盖）
- 未知 `kind` 的错误经 `HubError::Json` 报告，Display 消息含 serde 的 `unknown variant ... expected one of ...`（已验证）

## 扩展方向（可选）

- 给 `define_events!` 增加「校验」参数（如 `amount > 0` 的表达式注入 `validate() -> Result<(), HubError>`）——roadmap 推荐项目三选二的「校验」分支
- 事件加时间戳字段，`render()` 输出 RFC 3339 时间——时间与工具链主题见 roadmap 第 16 节（目录待建）
- 把 `HubEvent` 改成由宏生成（宏里自动建对应 variant 的枚举）——练习「宏生成类型 + 类型生成宏」的进阶，自写过程宏是宏方向的下一步（见主文档 3.7 与第 5 章）
- 用 cargo expand 观察本项目 `define_events!` 与 derive 的联合展开（cargo-expand 已实测可用，命令见 examples/README）
