# exercises —— 文件操作与异常处理阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。参考实现都在临时目录内构造测试数据，可直接 `python3 sol-XX-*.py` 运行验证。

完成顺序建议：按 1~5 顺序完成。

## 练习 1：读配置文件（★）

- **目标**：手动解析 INI 风格配置文件，输出 `{section: {key: value}}` 嵌套 dict
- **要求**：
  - 支持 `#` 注释行、空行、`[section]` 小节、`key = value` 键值对
  - 无法识别的行打印行号并跳过（不中断程序）
  - 文件读写用 `with open(..., encoding="utf-8")`
- **验收**：解析给定样例配置输出嵌套 dict；配置中含一条非法行时程序不崩溃，并输出带行号的警告

## 练习 2：解析 CSV（★★）

- **目标**：用 `csv.DictReader` 统计 CAN 日志中每个 CAN ID 的出现次数
- **要求**：
  - 按列名访问字段（不用 `row[0]` 索引）
  - 用 `collections.Counter` 统计，按次数降序输出
  - 捕获 `FileNotFoundError` 与 `csv.Error`
- **验收**：给定样例 CSV 输出每个 CAN ID 的出现次数，数量正确且降序排列

## 练习 3：读取 JSON（★★）

- **目标**：车辆配置 JSON round-trip（读入 → 修改 → 写回 → 重读验证）
- **要求**：
  - 用 `json.load`/`json.dump` 读写，写入时用 `indent=2, ensure_ascii=False`
  - 定义自定义异常（继承 `Exception`），文件缺失/格式错误时 `raise X from e` 保留根因
- **验收**：round-trip 后新增字段在重读文件中存在且值正确；文件缺失时抛出自定义异常，可从 `e.__cause__` 看到原始错误

## 练习 4：日志分析（★★★）

- **目标**：用正则统计 ERROR 级别按部件的故障频率，输出 Top-3
- **要求**：
  - 预编译正则（`re.compile`），提取时间/级别/部件/消息
  - 只统计 ERROR 行；无法匹配的行忽略（不崩溃）
  - 结果用 `Counter.most_common(3)` 输出
- **验收**：给定样例日志输出 Top-3 且计数正确；混入的非法行不影响结果

## 练习 5：批量重命名（★★★）

- **目标**：批量修改文件扩展名，支持 dry-run 预览与冲突检测
- **要求**：
  - 定义 `BatchRenameError` 自定义异常（继承 `Exception`），携带失败文件路径
  - `dry_run=True` 时只预览不实际操作
  - 目标文件已存在时抛 `BatchRenameError`；`OSError` 用 `raise ... from e` 包装
- **验收**：dry-run 不改变目录内容；冲突场景抛出 `BatchRenameError` 且保留根因

> **提示**：练习 1~5 与主文档第 6 章示例主题一一对应（读配置 / CSV / JSON / 日志 / 重命名），先独立完成，再对照 `examples/` 检查思路。`sol-*` 为参考实现，做完再看。
