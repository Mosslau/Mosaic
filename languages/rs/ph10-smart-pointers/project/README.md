# ph10 阶段项目：规则树执行器

对应 roadmap ph10 推荐项目「规则树执行器：用 Box 表达递归规则，用 Rc 共享规则元数据」。在主文档第 6 章示例的基础上扩展为"规则树求值 + 递归统计 + 树渲染 + 11 个单元测试"的完整版本。

## 需求

智能指针三大用途（堆分配、共享所有权、递归类型）在"规则引擎"里天然汇合：规则可以无限嵌套（And/Or/Leaf），必须用 `Box` 打破递归类型；规则元数据（名称、权重）会被多个规则节点复用，必须用 `Rc` 共享——这正是「用 `Box` 表达递归规则，用 `Rc` 共享规则元数据」的项目立意。

- `RuleMeta`：规则元数据（名称、权重），经 `Rc` 共享，一处修改、处处生效
- `RuleNode`：递归规则树——`Leaf(Rc<RuleMeta>)` / `And(Vec<Box<RuleNode>>)` / `Or(Vec<Box<RuleNode>>)`，`Box` 让无限嵌套合法
- `eval(&self, ctx: &RuleCtx) -> bool`：在事实集（`HashMap<&'static str, bool>`）下求值——Leaf 查表（缺省 false）、And 全真、Or 任一真
- `node_count()` / `weight()`：递归统计节点总数与权重总和（同一份共享元数据被多处引用时重复计入）
- `render(indent)`：带缩进的树形打印

## 功能清单

| 功能 | 说明 |
|------|------|
| 递归规则树 | `And` / `Or` / `Leaf` 无限嵌套，`Box<RuleNode>` 打破递归大小 |
| 元数据共享 | `RuleMeta` 经 `Rc` 共享，`strong_count` 实测 3（局部 + 两处 Leaf 引用） |
| 规则求值 | `eval`：Leaf 查事实表（缺省 false）、And 全真、Or 任一真，支持任意深度嵌套 |
| 递归统计 | `node_count`（本例 5）、`weight`（本例 25，共享元数据重复计入） |
| 树渲染 | `render` 带缩进输出树形结构 |
| 单元测试 | `#[cfg(test)]` 模块 11 个用例：Leaf 查表、And/Or 逻辑、嵌套、空上下文、计数、权重、Rc 共享计数、渲染、单节点边界 |

## 验收标准

- [ ] `rustc --edition 2021 src/main.rs -o /tmp/proj && /tmp/proj` 编译零警告，输出规则树、三组求值结果（true/true/false）、节点数 5、总权重 25、`auth_meta strong = 3`
- [ ] `rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test` 全部测试通过（11 个用例）
- [ ] 规则树只用 `Box` / `Rc` 表达递归与共享，全程安全代码（无 `unsafe`、无裸指针）
- [ ] 求值语义正确：Leaf 事实缺省 false、And 要求全真、Or 任一真即可，嵌套深度不受限

## 扩展方向（可选）

- 增加 `Not` 节点与短路求值（`And` 遇 false 即停、`Or` 遇 true 即停），观察短路对 `weight` 统计语义的影响
- 把 `Rc` 换成 `Arc` 并配合 `Mutex` 共享求值上下文（`Arc<Mutex<RuleCtx>>`），让规则树跨线程并发求值（衔接 ph12 并发与异步阶段，ph12 目录待建）
- 给 `RuleMeta` 加 `description` 字段支持日志输出；把 `render` 输出改成 JSON/规则 DSL，对接真实规则引擎（衔接 ph07 trait 与泛型阶段的 `Display`/`Serialize` 思路）
- 用 `eval` 的 `Option` 化结果区分"事实缺失"与"事实为假"，为规则命中审计铺路（衔接 ph11 错误处理与工程质量阶段）

## 验证环境

- rustc 1.92.0（macOS arm64），零第三方依赖
- 编译：`rustc --edition 2021 src/main.rs -o /tmp/proj`
- 运行：`/tmp/proj`
- 测试：`rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test`
- 验证状态：已验证（编译零警告，11 个单元测试全部通过）
