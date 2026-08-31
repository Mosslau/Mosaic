# ph08 Lambda 与 Stream 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-score-filter.java`）与类名（`ScoreFilter`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-score-filter.java
# 2. 运行（注意是类名不是文件名）
java ScoreFilter
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-score-filter.java | ScoreFilter | 过滤学生成绩：filter 过滤及格 + map 取姓名 + mapToInt 统计平均分/最高分/及格率 | `javac ex01-score-filter.java` | `java ScoreFilter` |
| ex02-group-by-class.java | GroupByClass | 按班级分组：groupingBy + summarizingInt 一次算出各班人数/平均/最高/最低，再按平均分排名 | `javac ex02-group-by-class.java` | `java GroupByClass` |
| ex03-device-filter.java | DeviceFilter | 设备状态筛选：Predicate.and 组合条件，findFirst + Optional.orElse/orElseThrow 处理查无设备 | `javac ex03-device-filter.java` | `java DeviceFilter` |
| ex04-log-stream.java | LogStream | 日志过滤统计：Files.lines 逐行读入 + Stream 过滤清洗 + groupingBy 分组计数（衔接 ph07） | `javac ex04-log-stream.java` | `java LogStream` |
| ex05-switch-modern.java | SwitchModern | 传统 switch 穿透对照 + Switch Expressions（`->`/`yield`）+ instanceof 模式匹配 | `javac ex05-switch-modern.java` | `java SwitchModern` |
| ex06-switch-pattern-matching.java | SwitchPatternMatching | switch 模式匹配 + `case null` + 类型模式分派（**需 JDK 21+**） | `javac ex06-switch-pattern-matching.java` | `java SwitchPatternMatching` |

## 验证状态

- ex01 ~ ex05：已在本环境用 OpenJDK 17.0.18 编译运行验证（零错误，输出符合预期）。
- ex06：**未在本环境验证**——switch 模式匹配（`case null`、类型模式分派）正式化于 Java 21（JEP 441；17~20 为预览，需 `--enable-preview`，JEP 406）；按文档命令（裸 `javac`）在本环境 OpenJDK 17.0.18 无法编译，代码语法按 JEP 441 正式规范书写，在 JDK 21+ 上可直接编译运行，预期输出见文件内 main 的行尾注释。

两点说明：

- ex04 运行时会自造测试文件 `app.log`，运行结束自动删除，无需手动清理。
- 所有示例的类都不是 `public`——这是 kebab-case 文件名与 Java「public 类必须与文件名同名」约束协调的结果（详见上文说明），`java` 运行不要求主类为 public。
