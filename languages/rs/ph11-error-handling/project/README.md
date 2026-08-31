# ph11 阶段项目：可靠 CLI（成绩报告生成器）

对应 roadmap ph11 推荐项目「可靠 CLI：读取文件、解析数据、输出报告，并提供清晰错误提示」。在主文档第 6 章示例 2/3（自定义错误 + 错误链）的基础上，落地为带**错误模型 + 退出码 + 单元测试**的完整命令行程序。

## 需求

输入一个文本文件，每行一条 `姓名,分数`（分数 0-100，空行忽略）。程序解析、校验、聚合（总数/总和/平均/最高/最低）并输出报告。重点不在聚合本身，而在**错误路径的工程质量**：任何一步出错（文件不存在、缺逗号、分数非数字、分数越界），都要给出「哪个文件、哪一行、什么值、底层原因」的可定位错误消息，并以非零退出码结束——这正是本阶段「错误信息能定位问题」验收点的完整形态。

- `ScoreError` 枚举：`Io` / `MissingComma { line, text }` / `BadScore { line, value, source }` / `OutOfRange { line, value }`——闭集错误模型，调用方可 `match` 穷尽
- `Display` 每条消息带行号/文件名；`Error::source()` 对 `Io`/`BadScore` 暴露底层原因；`From<io::Error>` 让 `?` 自动转换
- 错误链打印：`main` 失败时输出 `错误: <Display>` + `原因:` 逐层（source 遍历到根因）
- 退出码约定：成功 0、数据/IO 错误 1、用法错误 2

## 功能清单

| 功能 | 说明 |
|------|------|
| 逐行解析 | `parse_record`：缺逗号 / 非数字 / 越界分别报错，消息都带行号 |
| 文本解析核心 | `parse_text`：空行合法跳过、遇错短路，与文件 I/O 解耦（可单测直接喂文本） |
| 文件读取 | `load_scores`：`io::Error` 经 `From` 自动转 `ScoreError::Io` |
| 报告聚合 | `build_report`：总数 / 总和 / 平均（1 位小数）/ 最高 / 最低 |
| 清晰错误提示 | stderr 输出 `错误: <消息>` + 错误链逐层 `原因:`，退出码 1 |
| 用法校验 | 参数个数不对时打印用法并退出码 2 |
| 单元测试 | `#[cfg(test)]` 8 个用例：正常路径 ×2、异常路径 ×4、聚合 ×1、错误链 ×1 |

## 验收标准

- [ ] `rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj` 编译零警告
- [ ] `rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test` 全部测试通过（8 个用例，`test result: ok. 8 passed; 0 failed`）
- [ ] 正常文件（`Alice,90` / `Bob,75` / `Cara,80`）输出报告并退出码 0（实测：`成绩报告（共 3 条）`、`总分: 245, 平均: 81.7, 最高: 90, 最低: 75`）
- [ ] 坏行文件（第 2 行 `Bob,abc`）stderr 输出 `错误: 第 2 行分数 "abc" 不是数字: invalid digit found in string` + `原因: invalid digit found in string`，退出码 1（实测）
- [ ] 文件不存在时 stderr 输出 `错误: 读取文件失败: No such file or directory (os error 2)` + `原因: No such file or directory (os error 2)`，退出码 1（实测）
- [ ] 无参数时打印用法，退出码 2（实测）
- [ ] 全程安全代码：无 `unsafe`、无裸 `unwrap`（仅测试中的 `unwrap_err`/`unwrap` 属断言写法）

## 扩展方向（可选）

- 把 `ScoreError` 换成 `thiserror` 派生宏（`#[error(...)]`/`#[from]`，主文档 3.5，未在本环境验证需第三方 crate）——体会手写三步与 derive 的等价性
- 支持多文件合并、输出到文件、`--json` 结构化输出（把错误也做成结构化，衔接 ph12 的日志可观测性）
- 分数校验放宽为可配置区间（`--min`/`--max`），把「校验规则」变成错误枚举的一个新变体
- 用 `tracing` 记录处理过程（主文档 3.7，未在本环境验证需第三方 crate）

## 验证环境

- rustc 1.92.0（macOS arm64），零第三方依赖
- 编译：`rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj`
- 运行：`/tmp/proj <文件路径>`
- 测试：`rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test`
- 验证状态：已验证（编译零警告，8 个单元测试全部通过；各退出码场景输出为实测）
