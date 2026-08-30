# ph04 集合框架 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-student-manager.java`）与类名（`StudentManager`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-student-manager.java
# 2. 运行（注意是类名不是文件名）
java StudentManager
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-student-manager.java | StudentManager | List 管理学生：增删改查、排序、removeIf 安全删除 | `javac ex01-student-manager.java` | `java StudentManager` |
| ex02-word-freq.java | WordFreq | Map 统计词频：getOrDefault + 找最高频词 | `javac ex02-word-freq.java` | `java WordFreq` |
| ex03-set-dedup.java | SetDedup | Set 去重：LinkedHashSet 保序 / TreeSet 排序 / HashSet 交集 | `javac ex03-set-dedup.java` | `java SetDedup` |
| ex04-task-scheduler.java | TaskScheduler | PriorityQueue 任务调度 + TopK | `javac ex04-task-scheduler.java` | `java TaskScheduler` |
| ex05-lru-cache.java | LRUCache | LRU Cache：accessOrder + removeEldestEntry | `javac ex05-lru-cache.java` | `java LRUCache` |

全部已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，输出符合注释中的期望值）。两点说明：

- `ex02-word-freq.java` 的词频表按 `HashMap` 内部顺序打印，运行结果顺序可能与注释展示不同，属正常现象；只有「最高频词: the」可断言。
- `ex04-task-scheduler.java` 的 TopK 结果直接打印 `PriorityQueue` 的堆内部数组顺序，集合内容固定为 `{5, 6, 9}`，但打印顺序不保证。
