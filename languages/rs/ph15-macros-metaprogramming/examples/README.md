# examples —— 宏与元编程阶段完整示例

对应主文档 `15-macros-metaprogramming.md` 第 6 章示例 1~7。分成两组：

- **ex01~ex05（macro_rules! 声明宏，纯 std）**：零第三方依赖，`rustc --edition 2021 -D warnings` 单文件编译，产物输出 `/tmp/`。
- **ex06~ex07（serde / thiserror derive）**：第三方 crate，独立 cargo 工程 `crates/`，经 rsproxy 国内镜像拉取；cargo-expand 观察宏展开也在此工程实测。

验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20（**已验证**，经 rsproxy 拉取，Cargo.lock 锁定）；cargo-expand 1.0.126（**已验证**，安装方式见下文）。

## 第一组：macro_rules!（rustc 单文件，零依赖）

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-macro-basics.rs` | 示例 1 | 声明宏入门：定义/调用、三种调用括号（`()` `[]` `{}`）、宏生成表达式与语句、多臂匹配、`stringify!` 观察「宏收到的是 token」 | `rustc --edition 2021 -D warnings ex01-macro-basics.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-macro-metavariables.rs` | 示例 2 | 片段分类符实测：`expr`/`ident`/`ty`/`pat`/`literal`；多臂匹配「先匹配先得」 | `rustc --edition 2021 -D warnings ex02-macro-metavariables.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-macro-repetition.rs` | 示例 3 | repetition（重复展开）：`$(…)*`/`+`/`?` 与分隔符、尾逗号、编译期参数计数、空调用单独一臂 | `rustc --edition 2021 -D warnings ex03-macro-repetition.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-macro-hygiene.rs` | 示例 4 | 卫生性实测：宏内变量不泄漏到调用方；传入的 `ident` 指向调用方（参数不卫生是特性） | `rustc --edition 2021 -D warnings ex04-macro-hygiene.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-macro-errors.rs` | 示例 5 | **声明宏典型编译错误（故意编译失败，首行注释写明运行前提）**：一次编译实测三个错误 | `rustc --edition 2021 -D warnings ex05-macro-errors.rs -o /tmp/ex05`（**预期失败**） | —（不运行） |

## 第二组：serde / thiserror derive（cargo 工程 `crates/`，已验证）

`crates/` 是独立 cargo 工程（`Cargo.toml` 声明 serde/serde_json/thiserror，`Cargo.lock` 已提交锁定版本）。国内网络实测步骤：

```bash
# 1. 配置国内镜像（一次即可）：写入 $CARGO_HOME/config.toml
#    [source.crates-io]
#    replace-with = "rsproxy"
#    [source.rsproxy]
#    registry = "sparse+https://rsproxy.cn/index/"
# 2. 构建与运行（CARGO_TARGET_DIR 指向 /tmp，仓库零二进制残留；CARGO_HOME 指向临时目录则连注册表缓存也不落仓库）
cd examples/crates
CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex06-serde-derive
CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex07-thiserror-derive
```

| 文件 | 对应示例 | 说明 | 实测输出要点 |
|------|---------|------|-------------|
| `src/bin/ex06-serde-derive.rs` | 示例 6 | serde derive：`#[derive(Serialize, Deserialize)]` 生成序列化代码；`#[serde(rename_all = "camelCase")]` 字段改名、`skip_serializing_if` 跳过 None、缺字段 default（已验证 serde 1.0.229 / serde_json 1.0.151） | 序列化 `{"host":"127.0.0.1","port":8080,"maxConnections":512,"tlsCert":"cert-a"}`（tls_cert=None 时无 `tlsCert` 键）；类型错误 `invalid type: string "oops", expected u16 at line 1 column 25` |
| `src/bin/ex07-thiserror-derive.rs` | 示例 7 | thiserror derive：`#[derive(Error)]` 自动实现 Error + Display + source；`#[error("…{path}…")]` 消息模板；`#[from]` 生成 `From<io::Error>` 让 `?` 自动转换（已验证 thiserror 2.0.20） | `端口 70000 越界（合法范围 1-65535）`；`?` 自动转换 `io.kind() = NotFound`；source 链 `["IO 错误: No such file or directory (os error 2)", "No such file or directory (os error 2)"]` |

## cargo expand 观察宏展开（已验证，cargo-expand 1.0.126）

roadmap 练习「用 cargo expand 观察宏展开」。cargo-expand 安装（经 rsproxy，已实测）：

```bash
CARGO_HOME=/tmp/cargo-expand-home cargo install cargo-expand --locked   # 产物在 $CARGO_HOME/bin/cargo-expand
export PATH="$CARGO_HOME/bin:$PATH"
```

在 `examples/crates` 下观察 ex06 的 derive 展开（底层是 `rustc -Zunpretty=expanded`，cargo expand 只是包装 + 处理过程宏）：

```bash
cd examples/crates
CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo expand --bin ex06-serde-derive
```

实测展开摘录（逐字摘自实测输出；为可读性在行内补了 `//` 标注，标注不是展开产物本身。关键点：`#[serde]` 属性被翻译成真实的序列化代码，`rename_all` 的效果是字段名字符串直接变成 `"maxConnections"`，`skip_serializing_if` 变成 `if !Option::is_none(...)` 分支）：

```text
const _: () = {                       // derive 生成的 impl 包在匿名 const 里，不污染命名空间
    #[allow(unused_extern_crates)]
    extern crate serde as _serde;     // 路径卫生：显式引入 _serde，绝不依赖调用方作用域
    #[automatically_derived]
    impl _serde::Serialize for ServerConfig {
        fn serialize<__S>(&self, __serializer: __S) -> _serde::__private229::Result<…> {
            let mut __serde_state = _serde::Serializer::serialize_struct(
                __serializer, "ServerConfig",
                false as usize + 1 + 1 + 1
                    + if Option::is_none(&self.tls_cert) { 0 } else { 1 },
            )?;                          // 字段个数按 skip 条件动态算
            _serde::ser::SerializeStruct::serialize_field(&mut __serde_state, "host", &self.host)?;
            _serde::ser::SerializeStruct::serialize_field(&mut __serde_state, "maxConnections", &self.max_connections)?;
            //                                       ^^^^^^^^^^^^^ rename_all 生效点
            if !Option::is_none(&self.tls_cert) {   // skip_serializing_if 生效点
                _serde::ser::SerializeStruct::serialize_field(&mut __serde_state, "tlsCert", &self.tls_cert)?;
            } else {
                _serde::ser::SerializeStruct::skip_field(&mut __serde_state, "tlsCert")?;
            }
            _serde::ser::SerializeStruct::end(__serde_state)
        }
    }
};
```

`Deserialize` 侧还会生成一个内部 `__Field` 枚举 + `__FieldVisitor`（serde 用「访问者模式」做反序列化的字段派发）。单文件 `macro_rules!` 示例想看展开，直接用 rustc 的 `-Zunpretty=expanded`（cargo expand 同款底层，已实测，`ex01` 的展开见主文档第 4 章）：

```bash
RUSTC_BOOTSTRAP=1 rustc --edition 2021 -Zunpretty=expanded ex01-macro-basics.rs
```

## 实测输出要点

- **ex01**：`hello, rust!` ×3（三种括号）、`double!(10 + 11) = 42`、`classify!(0) = zero, classify!(42) = nonzero`、`show: 10 + 11 = 21`、`show: vec![1, 2, 3].len() = 3`。
- **ex02**：`counter = 41`、`bignum = 42`、`map.is_empty() = true`、`matches_some!(Some(7), Some(_)) = true` / `None` 版 `false`、`is_zero!(0)` 命中第一臂 / `is_zero!(7)` 命中第二臂。
- **ex03**：`my_vec![1, 2, 3, 4] = [1, 2, 3, 4], len = 4`、空调用 `[]`、尾逗号断言通过、`echo_args!` 打印 `arg 1: 2 + 3 = 5`、`count_args!(a, b, c, d, e) = 5`、`min_len_2!(1, 2, 3) 参数个数 = 3`。
- **ex04（卫生性实测）**：调用方 `secret = 7` 与宏内 `secret = 42` 互不干扰（断言通过：宏内变量未泄漏）；`bump!(counter, 5)` 通过传入 ident 把调用方 `counter` 改成 5。
- **ex05（预期编译失败，一次编译报三个错误，rustc 1.92.0 实测）**：
  - `error: meta-variable `a` repeats 3 times, but `b` repeats 2 times`（两个独立 repetition 在同一层混用，展开次数不一致）；
  - `error: expected expression, found `$``（展开体引用了未声明的元变量 `$undeclared`）；
  - `error[E0425]: cannot find value `total` in this scope`（卫生性边界：宏体里直接写调用方局部变量名，解析发生在宏定义处作用域，提示定位到宏调用处）。
- **ex06**：见上表（序列化 JSON 两形态、往返一致、类型错误行列定位）。
- **ex07**：见上表（Display 模板、dyn Error 装箱、`?` 自动转换、source 链）。

## 运行注意事项

- **ex05 不会编译通过**——它是「声明宏典型错误」的实测证据文件；错误文本随 rustc 版本可能微调，文档记录的是 rustc 1.92.0 实测值（三个错误）。
- ex06/ex07 的输出与字段顺序确定（serde 结构体序列化按声明顺序），类型错误消息的行列号随 JSON 文本固定，均为确定值。
- cargo 首次构建需联网（crates.io 或 rsproxy）；`Cargo.lock` 已提交，版本按锁文件拉取。
- 全部编译产物输出到 `/tmp/`（或 `CARGO_TARGET_DIR`），仓库内零二进制残留。

## 验证状态汇总

- ex01~ex04：`rustc --edition 2021 -D warnings` 编译零警告并运行验证（已验证）。
- ex05：预期编译失败，三个错误的错误文本实测后写入（已验证）。
- ex06/ex07：serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20 经 rsproxy 拉取并完整编译运行（已验证）。
- cargo expand：cargo-expand 1.0.126 安装并实测（已验证）；`rustc -Zunpretty=expanded` 底层机制同样实测。
