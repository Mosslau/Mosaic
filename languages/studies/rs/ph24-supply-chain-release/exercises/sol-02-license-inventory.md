# sol-02 —— 整理许可证清单参考实现

> 练习对象为 `examples/ex01-cargo-audit/vulndemo/`（依赖锁在 time 0.1.35）。下方 license 元数据来自 `cargo deny list` 与 `cargo metadata` 的**本机实测**（2026-09-04）。SPDX 语义判定按主文档 3.6。

## 步骤 1：跑命令取数

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd examples/ex01-cargo-audit/vulndemo
cargo deny list        # 需要先有 deny.toml（见 sol-01）；或 ./check-licenses.sh .（examples/ex03）
```

实测（`cargo deny list` 输出）：

```text
Apache-2.0 (2): libc@0.2.189, time@0.1.35
MIT (5): kernel32-sys@0.2.2, libc@0.2.189, time@0.1.35, winapi@0.2.8, winapi-build@0.1.1
Unlicensed (1): ph24-vulndemo@0.1.0
```

## 步骤 2：SPDX 表（许可证 × crate × 声明类型）

按 crate 侧核对 `cargo metadata` 的 license 字段，声明类型分「标准 SPDX」「老式写法」「缺失」三档：

| crate（版本） | license 声明（cargo metadata） | 声明类型 | 归类许可（SPDX） |
|--------------|-------------------------------|---------|-----------------|
| ph24-vulndemo (0.1.0) | 无 | **缺失** | —（发布前必须补） |
| time (0.1.35) | `MIT/Apache-2.0` | 老式斜杠写法 | MIT OR Apache-2.0 |
| libc (0.2.189) | `MIT OR Apache-2.0` | 标准 SPDX 表达式 | MIT OR Apache-2.0 |
| kernel32-sys (0.2.2) | `MIT` | 标准 SPDX | MIT |
| winapi (0.2.8) | `MIT` | 标准 SPDX | MIT |
| winapi-build (0.1.1) | `MIT` | 标准 SPDX | MIT |

逆查表（许可证 → crate，即 `cargo deny list` 的视角）：

| 许可证 | 使用它的 crate |
|--------|---------------|
| Apache-2.0 | libc 0.2.189、time 0.1.35（后者为 OR 分支） |
| MIT | kernel32-sys 0.2.2、libc 0.2.189、time 0.1.35、winapi 0.2.8、winapi-build 0.1.1 |
| （无）Unlicensed | ph24-vulndemo 0.1.0 |

## 步骤 3：两种分发模式的判定

**模式 A：内部应用**（allow = MIT/Apache-2.0/BSD-3/ISC/MPL-2.0/0BSD/Unicode-3.0/Zlib 一类宽松集合）
- 第三方依赖 5 个：MIT / Apache-2.0 / MIT-OR-Apache 全部命中 → 通过；
- **卡点唯一在根包自己**：ph24-vulndemo 未声明 license → Unlicensed。内部应用若不分发源码影响小，但作为库作者仍应补（缺失的根包 license 会在发布/被下游审计时拦住别人，也拦住你）。
- 行动项：给 `Cargo.toml` 补 `license = "MIT OR Apache-2.0"` 并放 LICENSE 文件。

**模式 B：闭源商业分发**（上档 + 逐例评估）
- 第三方依赖同为宽松许可 → 通过；
- 行动项同上 + 建议给依赖树跑一遍 `cargo deny check licenses`（门禁）而非一次性脚本，防止升级时漂移。

## 验收对照

- [x] SPDX 表完整（许可证 × crate × 声明类型）
- [x] 两种分发模式的判定有明确结论 + 具体行动项
- [x] 识别出「老式写法」与「缺失」两类脏数据，并说明其在 deny/脚本下的不同命运（OR 拆解命中 vs unlicensed error）
