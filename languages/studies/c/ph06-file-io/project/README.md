# 阶段项目：CSV 解析器

对应 roadmap ph06 推荐项目第一个「CSV 解析器」。解析 `name,age,score` 三列 CSV，支持坏行报告、统计输出与按字段聚合，为后续日志系统提供数据输入。

## 需求

- `csv_parse()` —— 解析整个文件：逐行读取、剔除行尾、跳过空行、字段数/数字格式/长度三重校验，坏行记录行号与原因
- `csv_stats()` —— 统计有效记录数、跳过行数与失败原因分布
- `csv_print()` —— 打印有效记录
- `csv_free()` —— 释放记录数组
- 支持按成绩排序输出（`-s` 参数）——为 ph21 排序算法的应用打底

## 功能清单

| 功能 | 说明 |
|------|------|
| 三列校验 | `name,age,score`，拒绝多余/缺少列 |
| 数字校验 | `sscanf` 返回值检查 age/score |
| 长度校验 | name 超 31 字节拒绝 |
| 坏行报告 | 行号 + 原因（字段数错误/数字格式错误/名字过长） |
| 排序输出 | `-s` 按 score 降序（qsort + 比较函数） |
| 样例数据 | 自带 `students.csv`（含空行/坏行/多余列） |

## 验收标准

- [ ] `gcc -Wall -Wextra -std=c99 csv_parser.c main.c -o csvparser` 编译零警告
- [ ] `./csvparser students.csv` 输出有效记录 + "共 N 行: 有效 X 条, 跳过 Y 行"
- [ ] `./csvparser -s students.csv` 按成绩降序输出
- [ ] `./csvparser missing.csv` 优雅报错（perror + 退出码 1）
- [ ] `valgrind --leak-check=full ./csvparser students.csv` 无泄漏

## 扩展方向

- 支持任意列数（动态字段数），对齐 ph21 的通用解析
- 支持字段内引号转义与逗号（状态机解析，主文档示例 2 已预告 ph16）
- 输出到 CSV（`csv_write`），做 ETL 管道的一环

## 验证环境

- Apple clang 17（gcc 兼容），`-Wall -Wextra -std=c99`
- 编译：`gcc -Wall -Wextra -std=c99 csv_parser.c main.c -o csvparser`
- 运行：`./csvparser students.csv` / `./csvparser -s students.csv`
- 验证状态：已验证
