# 迁移项目：购物篮规则筛选

## 需求

1. 生成 300 个购物篮；
2. Apriori 挖频繁项集与规则；
3. 按 `lift≥1.1`、`confidence≥0.8` 过滤；
4. 输出可执行的交叉销售候选。

## 验收

- 规则数 >0；
- 过滤后规则 ≥3；
- 说明共现≠因果。

## 运行

```bash
cd algorithms/p02-statistical-ml/association-rules/project
uv run python basket_rules.py
```

## 实测

规则 534，过滤后 214；Top：`{banana,bread}→milk`、`{coffee,butter}→sugar`。

结论：可用于候选生成；上线前需 A/B/因果验证。
