# ph07 IO 与文件操作 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-read-config.java`）与类名（`ReadConfig`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-read-config.java
# 2. 运行（注意是类名不是文件名）
java ReadConfig
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-read-config.java | ReadConfig | 读取配置文件：Files.readAllLines + 手写 key=value 解析，忽略空行与 # 注释 | `javac ex01-read-config.java` | `java ReadConfig` |
| ex02-log-analyzer.java | LogAnalyzer | 日志分析：BufferedReader 逐行 + 正则统计 ERROR 总数与各错误出现次数 | `javac ex02-log-analyzer.java` | `java LogAnalyzer` |
| ex03-csv-parser.java | CsvParser | CSV 解析：Scanner 按行 + split，简单处理引号字段并计算平均分 | `javac ex03-csv-parser.java` | `java CsvParser` |
| ex04-batch-rename.java | BatchRename | 批量重命名：Files.walk 遍历目录树，所有 .log 改名为 .txt | `javac ex04-batch-rename.java` | `java BatchRename` |
| ex05-object-serialization.java | ObjectSerialization | 对象序列化：Serializable + transient + serialVersionUID，password 不落盘 | `javac ex05-object-serialization.java` | `java ObjectSerialization` |

全部已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，输出符合预期）。两点说明：

- 各示例运行时会自造测试文件（`app.properties` / `app.log` / `scores.csv` / `logs/` / `user.ser`），运行结束自动删除，无需手动清理。
- 所有示例的类都不是 `public`——这是 kebab-case 文件名与 Java「public 类必须与文件名同名」约束协调的结果（详见上文说明），`java` 运行不要求主类为 public。
