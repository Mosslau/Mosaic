# ph08 阶段项目：只读配置视图

对应 roadmap ph08 推荐项目「只读配置视图：从配置文本中借用字段并提供查询接口」。在主文档示例 2 的基础上扩展为 section 分组、通用 `get(key)` 查询与行号定位，并附单元测试。

## 需求

数据基础设施里，服务启动时要读一份 `key=value` 配置文本并反复查询。如果每次查询都复制出 `String`，既浪费内存又让所有权关系变复杂。本项目实现一个**零拷贝的只读视图**：解析阶段不复制任何字段，所有 key/value 都是指向原文的 `&'a str` 切片，查询接口直接返回切片。这是生命周期阶段的核心套路——**视图与原文同生共死**：

- `Entry<'a>`：单条配置（section、key、value、行号），字段全部借用原文
- `ConfigView<'a>`：持有 `Vec<Entry<'a>>`，`parse(text: &'a str) -> ConfigView<'a>` 把输入借用与视图绑定同一个 `'a`
- 解析规则：支持 `[section]` 分组、`#` 注释、空行；全局 key 与 section 内 key 互不干扰
- 查询接口：`get(key) -> Option<&'a str>`（支持 `"key"` 与 `"section.key"` 两种形式）、`lineno_of(key)`、`section(name)`、`len()`
- 教学要点：`get` 返回 `&'a str`（绑定原文）而非 `&self` 的切片——视图 drop 后取出的切片仍有效（有对应单元测试）

## 功能清单

| 功能 | 说明 |
|------|------|
| 零拷贝解析 | `parse(&'a str)` 所有条目借用原文，无任何 String 复制 |
| section 分组 | `[db]` 头部切换分组，`db.host` 与全局 `host` 互不覆盖 |
| 注释与空行 | `#` 开头行与空行跳过，不计入条目 |
| 通用查询 | `get("key")` / `get("section.key")` 返回 `Option<&'a str>` |
| 行号定位 | `lineno_of(key)` 返回 key 在原文中的 1-based 行号 |
| section 列表 | `section(name)` 返回组内全部 `(key, value)` |
| 单元测试 | `#[cfg(test)]` 模块覆盖解析、分组隔离、缺失 key、行号、返回值生命周期 |

## 验收标准

- [ ] `rustc --edition 2021 src/main.rs -o /tmp/proj && /tmp/proj` 编译零警告，输出全局查询、分组查询、行号与条目统计
- [ ] `rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test` 全部测试通过（不少于 8 个用例）
- [ ] 结构体字段全部为 `&'a str` / `usize`，无任何 `String` 字段（零拷贝）
- [ ] `get("host")` 与 `get("db.host")` 返回不同值：section 不泄漏到全局
- [ ] `returned_slice_outlives_the_view` 测试通过：`get` 返回的切片在视图 drop 后仍有效（证明返回值绑定原文 `'a` 而非 `&self`）

## 扩展方向（可选）

- 再写一个拥有字段（`String`）版本 `OwnedConfig`，对比两者在"存进 `Vec` 长期持有"时的差异，体会「视图 vs 持有」的取舍（对照主文档示例 4）
- 文本索引视图：对日志文本建立「行号 → 行内容」借用视图，提供 `line(n) -> Option<&str>`（与本题同套路，可当作第二个项目）
- 用迭代器链重写 `section()` 与解析循环（衔接 ph09 集合、迭代器与函数式写法阶段）
- 解析失败（如无 `=` 的非空行）返回 `Result` 而非静默跳过（衔接 ph11 错误处理与工程质量阶段）
- 从文件读入配置文本（ph13 文件、网络与系统编程阶段），做成真实的配置加载器

## 验证环境

- rustc 1.92.0（macOS arm64），零第三方依赖
- 编译：`rustc --edition 2021 src/main.rs -o /tmp/proj`
- 运行：`/tmp/proj`
- 测试：`rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test`
- 验证状态：已验证（编译零警告，8 个单元测试全部通过）
