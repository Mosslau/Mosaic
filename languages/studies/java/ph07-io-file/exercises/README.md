# ph07 IO 与文件操作 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同，如 `sol-01-config-reader.java` 的类名是 `ConfigReaderSol`），编译用文件名、运行用类名，如 `javac sol-01-config-reader.java` + `java ConfigReaderSol`。

## 练习 1：读取配置文件（★）

**目标**：手写 `key=value` 配置解析，支持默认值与类型转换。
**要求**：
- 实现 `Map<String, String> loadConfig(String path)`：用 `Files.readAllLines`（显式 UTF-8）读入，跳过空行与 `#` 注释行，按第一个 `=` 切分 key 与 value，两端去空白
- 实现 `String get(Map<String, String> config, String key, String defaultValue)` 与 `int getInt(...)`：key 不存在时返回默认值；`getInt` 对非法数字抛 `IllegalArgumentException` 且消息含 key 名
- main 中先用 `Files.write` 自造一个含注释、空行、含空格的配置文件再解析；最后清理测试文件
- **必须用 try-with-resources 或 Files 便捷方法**，不允许流泄漏
**验收**：解析结果中注释行与空行被忽略；`timeout= 30 `（两端空格）解析为 `30`；读取不存在的 key 返回默认值；`getInt` 对 `timeout=abc` 抛 `IllegalArgumentException` 且消息含 `timeout`。

## 练习 2：日志分析（★★）

**目标**：逐行分析日志文件，统计各级别行数与关键词出现次数，大文件内存占用恒定。
**要求**：
- 用 `BufferedReader`（显式 UTF-8 编码的 `InputStreamReader` 包装 `FileInputStream`）逐行读取，**禁止 `Files.readAllLines` 整体读入**
- 统计 INFO / WARN / ERROR 三个级别的行数；额外统计包含关键词（如「超时」）的行数
- 按出现次数从高到低输出每种 ERROR 消息（用正则提取 `ERROR ` 之后的文本），次数相同按字典序
- main 中自造一个至少含 8 行、三种级别的测试日志，分析后清理
**验收**：三个级别计数与测试数据一致；ERROR 消息按次数降序排列；源码中无 `readAllLines`/`readAllBytes`；能口述为什么逐行读取对几百 MB 日志内存安全。

## 练习 3：CSV 解析（★★）

**目标**：解析成绩表 CSV，计算平均分并按列筛选。
**要求**：
- 解析含表头的 CSV：`name,class,score`，逐行读取 + `split(",")`，字段去除首尾空白与成对引号
- 计算全体平均分（保留 1 位小数）；按班级分组，输出每个班级的平均分
- 对非法行（字段数不足、score 非数字）打印警告并跳过，不中断解析
- main 中自造 CSV（含一行非法数据），解析后清理
**验收**：合法行的平均分计算正确；非法行被跳过并打印警告；分组结果按班级名输出；能说明字段内含逗号（如 `"Doe, John"`）时 `split` 的局限与工业级替代方案（OpenCSV）。

## 练习 4：批量重命名（★★★）

**目标**：用 `Files.walk` 递归遍历目录树，批量给文件加前缀并改扩展名。
**要求**：
- 把目录树中所有 `.log` 文件改名为 `backup-原名.txt`（如 `sub/c.log` → `sub/backup-c.txt`）
- **必须用 try-with-resources 关闭 `Files.walk` 返回的流**；用 `Files.move` + `StandardCopyOption.REPLACE_EXISTING`
- 单个文件重命名失败只打印错误并继续，不中断整体流程；最后输出成功/失败计数
- main 中自造测试目录树（含子目录、含非 .log 文件），重命名后清理整棵树
**验收**：所有 `.log` 被重命名且非 `.log` 文件不受影响；输出计数与预期一致；运行后 `logs/` 目录被完整删除；能说明为什么遍历时不能边遍历边修改同一目录流（先收集再执行 vs 直接 forEach 的选择）。

> **提示**：四题与主文档第 6 章示例 1~4 主题一一对应——先独立完成，再对照 `examples/` 检查。`sol-*` 为参考实现（头注释已注明），做完再看。
