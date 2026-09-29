# 索引表格式规范

> 用于 `algorithms/README.md` 的索引表。
> `scripts/validate.py` 按本规范定义的**列序**解析——列序是契约，调整前必须先改本规范与脚本。
> 表格之外的链接（推荐顺序列表、blockquote 导航）不属于索引表，脚本不解析。
> engineering/ 两个平台的索引表列序契约见 `engineering-docs/references/index-format.md`（不归本 skill）。

## algorithms/README.md

按族分组（`## <NN-族> · <族名>` 标题下一张表），四列固定顺序：

```markdown
| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [<实验名>](<NN-族>/<算法名>/) | <X.Y.Z> | ⬜/🚧/✅ | <YYYY-MM-DD 或空> |
```

规则：

- 链接必须是相对 `algorithms/` 的目录链接，形如 `01-search/a-star/`（带不带结尾 `/` 均可）
- 章节号与该实验 README 的章节锚点一致（不一致时 validate.py 记 🟡）
- 状态符与该实验 README 状态行一致（不一致记 ❌）
- ✅ 必须填完成日期且与 README 状态行一致；⬜/🚧 日期留空

## 解析失败处理

表格行中出现链接（`](`）但不符合上述形态时，validate.py 记 🟡 警告而非静默跳过——
看到此类警告先对照本规范检查列序，再改脚本。
