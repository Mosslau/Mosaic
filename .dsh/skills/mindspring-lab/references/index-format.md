# 索引表格式规范

> 用于 `algorithms/README.md` 与 `engineering/ai-platform/README.md` 的索引表。
> `scripts/validate.py` 按本规范定义的**列序**解析——列序是契约，调整前必须先改本规范与脚本。
> 表格之外的链接（推荐顺序列表、blockquote 导航）不属于索引表，脚本不解析。

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

## engineering/ai-platform/README.md

一张项目总览表，五列固定顺序：

```markdown
| 阶段 | 项目 | 验收标准一句话 | 状态 | 完成日期 |
|---|---|---|---|---|
| <中文数字> | [<NN-项目>](<NN-项目>/) | <一句话可检验目标> | ⬜/🚧/✅ | <YYYY-MM-DD 或空> |
```

规则：

- 阶段用中文数字（一~七），与目录编号 NN 一致（validate.py 按目录编号 ↔ README 锚点核对）
- 链接是相对 `engineering/ai-platform/` 的目录链接，形如 `01-text-corpus-pipeline/`
- 状态与日期规则同 algorithms 线

## 解析失败处理

表格行中出现链接（`](`) 但不符合上述形态时，validate.py 记 🟡 警告而非静默跳过——
看到此类警告先对照本规范检查列序，再改脚本。
