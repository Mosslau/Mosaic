# ph08 阶段项目：日志过滤统计

## 需求

对应 Roadmap「ph08 Lambda 与 Stream 阶段」推荐项目第一个「日志过滤统计」：读取日志文件（衔接 ph07 IO 与文件操作阶段），用 Stream 过滤 ERROR/WARN、清洗行内容、按错误信息分组计数并输出 TopN；大文件用 `Files.lines` + try-with-resources 逐行处理保持内存恒定。项目覆盖本阶段全部核心知识点：Stream 流水线（filter/map/sorted/limit）、Collectors（groupingBy/counting/joining）、Optional（解析可能失败、最高频可能没有）、方法引用。

## 文件结构

| 文件 | 类 | 职责 |
|------|----|------|
| log-stats.java | LogStatsTool | 命令行入口 + 日志行解析 + 级别统计 / ERROR TopN + 报表输出 + 自测 main |

## 功能清单

- [ ] 日志行解析：`LogEntry` record（级别 + 消息），格式不合法的行返回 `Optional.empty()` 而非抛异常
- [ ] 级别统计：`groupingBy(level, counting())` 输出 INFO/WARN/ERROR 行数与占比，非法行被 `Optional::stream` 天然跳过
- [ ] ERROR TopN：过滤 ERROR → 按消息分组计数 → 按次数降序（次数相同按字典序）→ `limit(n)` 截取
- [ ] 报表输出：`Collectors.joining("\n")` 拼接 TopN 报表；`findFirst` + `ifPresent` 输出最高频错误
- [ ] 级别过滤：命令行第二参数指定级别（如 `ERROR`），打印该级别全部原始行
- [ ] 内存恒定：全程 `Files.lines` 逐行惰性处理，禁止 `readAllLines` 整读；每个流都在 try-with-resources 中关闭
- [ ] 自测 main：无参数运行时自造含非法行的测试日志，断言级别计数、TopN 顺序、无 ERROR 时不抛异常，失败抛 `AssertionError`

## 验收标准

- `javac log-stats.java` 编译零错误
- `java LogStatsTool` 全部自测通过，末尾打印「全部自测通过」，且运行后测试日志文件被清理
- 自测覆盖：INFO 2 / WARN 1 / ERROR 4 计数正确；非法行不产生级别；Top1 为「数据库连接超时 x3」；无 ERROR 的日志 TopN 为空列表
- 命令行用法：`java LogStatsTool <日志文件> [级别]`；文件不存在时明确报错并以非零码退出
- 源码中无 `readAllLines`/`readAllBytes`，无裸调 `Optional.get()`

## 扩展方向

- **并行加速**：数据量大时把统计流水线换成 `parallelStream` 观察加速比，注意终端归约必须线程安全（主文档 3.8、4.3 节；线程模型细节见 ph09 多线程与并发阶段）
- **时间窗口统计**：解析时间戳，按分钟/小时用 `groupingBy` 出错误趋势图（衔接 ph03 常用类阶段的时间 API）
- **CSV 报表导出**：用 `joining(",")` 把统计结果写成 CSV（衔接 ph07 的文件写出）
- **报表分组统计**：Roadmap 推荐项目第二个——对学生/订单/设备数据做 `groupingBy` + `summarizingInt` + `partitioningBy` 表格报表，examples/ex02 已给出核心句式

## 验证环境

- 工具链：OpenJDK 17.0.18（Homebrew，`javac -version` → 17.0.18）
- 编译：`javac log-stats.java`
- 运行：`java LogStatsTool`（自测）或 `java LogStatsTool <日志文件> [级别]`（命令行使用）

```bash
# 1. 编译
javac log-stats.java
# 2. 运行自测
java LogStatsTool
# 3. 验证后清理 .class
rm -f *.class
```

已在本环境用 OpenJDK 17.0.18 编译运行验证（零错误，自测全部通过）。
