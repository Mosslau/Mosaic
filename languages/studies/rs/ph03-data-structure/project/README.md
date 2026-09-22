# ph03 阶段项目：索引注册表

## 需求

对应 Roadmap「ph03 基础数据结构阶段」推荐项目之一：实现一个索引注册表，支持**新增索引**（名称、类型、列数）、**按名称查询**、**按类型统计**。核心用 struct 表达索引元数据、Vec 保存有序记录、HashMap 建立「名称 → 位置」映射，综合运用本阶段的 struct / Vec / HashMap / entry API。

## 功能清单

- [ ] `register`：新增索引，重名时拒绝并返回 `false`
- [ ] `get_by_name`：按名称查询，返回 `Option<&Index>`（不存在返回 `None`）
- [ ] `count_by_type`：按类型统计数量，返回 `HashMap<&str, usize>`
- [ ] `list_by_type`：按类型列出所有索引（示例 5 的扩展能力）
- [ ] 单元测试覆盖注册、查询、重名拒绝、统计、按类型列出

## 验收标准

- `rustc main.rs -o /tmp/index-registry` 编译零警告，`/tmp/index-registry` 运行输出正常
- `rustc --test main.rs -o /tmp/index-registry-test && /tmp/index-registry-test` 全部测试通过
- 重名注册返回 `false` 且不新增记录；查询不存在的名称返回 `None`
- 按类型统计与按类型列出的结果正确

## 扩展方向（可选）

- 支持删除索引（`remove`）：删除时同步维护 `by_name` 与 `indexes` 的位置映射
- 把 `index_type` 从 `String` 改成 `enum IndexType { Btree, Hash, Inverted }`，让非法类型无法构造（「使非法状态不可表示」，呼应 ph05 模式匹配）
- 支持按名称排序输出（`sort_by`）

## 验证环境

rustc 1.92.0（无第三方依赖）。编译：`rustc main.rs -o /tmp/index-registry`；运行：`/tmp/index-registry`；测试：`rustc --test main.rs -o /tmp/index-registry-test && /tmp/index-registry-test`。已在本环境验证。
