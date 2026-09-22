# ph08 Lambda 与 Stream 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同，如 `sol-01-score-stats.java` 的类名是 `ScoreStatsSol`），编译用文件名、运行用类名，如 `javac sol-01-score-stats.java` + `java ScoreStatsSol`。
> 五题与 Roadmap「ph08 Lambda 与 Stream 阶段」练习小节一一对应。

## 练习 1：过滤学生成绩并统计平均分（★）

**目标**：用一条 Stream 流水线完成「过滤及格 → 映射姓名 → 收集」，并对成绩做数值统计。
**要求**：

- 给定学生列表（姓名 + 分数），用 `filter` 保留 60 分及以上、`map` 取姓名、`collect(Collectors.toList())` 收集及格的名单
- 用 `mapToInt` 转基本类型流，统计全体学生的平均分、最高分、最低分
- 平均分用 `average()` 计算，**必须处理空集合情况**（`OptionalDouble` 用 `orElse(0)` 兜底，禁止裸调 `getAsDouble()`）
- 输出及格率（及格人数 / 总人数，百分比整数）
- **全程不允许出现 for 循环**处理集合

**验收**：对 `[("Alice",92), ("Bob",58), ("Cary",76), ("Dana",45)]`，及格名单为 `[Alice, Cary]`，平均分 67.8，最高分 92，及格率 50%；空列表输入时平均分输出 0 且不抛异常。

## 练习 2：按班级分组（★★）

**目标**：用 `groupingBy` + 下游收集器一次完成「分组 + 统计」，并对分组结果排序输出。
**要求**：

- 给定学生列表（班级 + 姓名 + 分数），用 `Collectors.groupingBy(班级, Collectors.summarizingInt(分数))` 得到每个班的 `IntSummaryStatistics`
- 输出每班的人数、平均分（1 位小数）、最高分、最低分
- 对分组结果按**平均分从高到低**输出排名（对 `entrySet().stream()` 排序）
- 加分项：用 `Collectors.joining(", ")` 把每班的姓名串成一行输出

**验收**：对 `[("一班","Alice",92), ("一班","Bob",58), ("二班","Cary",76), ("二班","Dana",88), ("三班","Eve",65)]`，二班平均 82.0 排第一、三班 65.0 排最后；每班四项统计量与手算一致。

## 练习 3：设备状态筛选（★★）

**目标**：用 `Predicate` 组合表达复合条件，用 `Optional` 处理「按 ID 查找可能不存在」。
**要求**：

- 给定设备列表（id + status[online/offline/fault] + battery[0-100]），定义 `Predicate<Device> isOnline` 与 `Predicate<Device> batteryOk`，用 `.and()` 组合筛出「在线且电量 ≥ 50」的可调度设备
- 实现按 id 查找：`filter` + `findFirst` 返回 `Optional<Device>`，查不到时用 `orElse` 返回一个兜底设备对象
- 实现按 id 取电量：`findFirst` → `map(取电量)` → `orElseThrow`（查不到抛 `IllegalStateException`，消息含设备 id）
- 演示 `orElse` 与 `orElseGet` 的区别：兜底逻辑里打一行日志，观察 `orElse` 在值存在时**仍执行**兜底逻辑、`orElseGet` 不执行

**验收**：对 `[("d-001","online",85), ("d-002","offline",60), ("d-003","online",30), ("d-004","fault",95)]`，可调度设备只有 d-001；查 d-999 返回兜底设备；取 d-001 电量输出 85；日志能清楚展示 `orElse`/`orElseGet` 的求值时机差异。

## 练习 4：用 Switch Expressions 重写 if-else 分支（★★）

**目标**：把「成绩分级」和「周几判断」两段 if-else/传统 switch 改写为 Switch Expressions，消除 break 与临时变量。
**要求**：

- `grade(int score)`：用 `switch (score / 10)` 表达式返回等级——90 以上优秀、80 良好、70 中等、60 及格、其余不及格；块体分支用 `yield` 处理 score 越界（<0 或 >100 返回「非法分数」）
- `dayLabel(int day)`：用箭头语法多值合并——`case 1, 2, 3, 4, 5 -> "工作日"`、`case 6, 7 -> "周末"`，其余 `default -> "非法日期"`
- **不允许出现任何 `break` 语句**；两个方法都必须直接 `return switch (...) {...}`
- 能对空枚举/边界输入说明「为什么 int 型 switch 表达式必须写 default」

**验收**：`grade(85)` → 良好、`grade(105)` → 非法分数、`grade(59)` → 不及格；`dayLabel(3)` → 工作日、`dayLabel(6)` → 周末、`dayLabel(9)` → 非法日期；源码全文无 `break`。

## 练习 5：用 Pattern Matching 改写 instanceof 判断（★★★）

**目标**：把一个「类型判断 + 强转」的事件分派方法改写为 instanceof 模式匹配，消除全部显式强转。
**要求**：

- 定义一个小型事件类型层次：如 `TextEvent(String content)`、`ClickEvent(int x, int y)`、`TimeoutEvent(long millis)`（可用多个 static 嵌套类）
- 实现 `String describe(Event e)`：旧版用 `instanceof` + 显式强转写成对照；新版用 `obj instanceof Type var` 模式匹配重写，**新版中不允许出现任何强转表达式**（`(Type)` 形式）
- 用模式变量的流式作用域写一条组合判断：`if (e instanceof TextEvent t && t.content.length() > 10)` 走「长文本」分支
- 处理 `null` 输入：新版中 `null` 匹配不到任何模式，走 else 分支输出「未知事件」，验证不抛 `NullPointerException`
- 加分项（需 JDK 21+，本阶段环境不满足可只写注释说明）：改用 switch 模式匹配 + `case null` 实现同一方法

**验收**：对 `TextEvent("hello")`、`TextEvent("超过十个字符的长文本内容")`、`ClickEvent(3, 4)`、`TimeoutEvent(5000)`、`null` 五种输入，新旧两版输出完全一致；新版源码中无显式强转；null 输入不抛异常。

> **提示**：五题与主文档第 6 章示例 1~5 主题一一对应——先独立完成，再对照 `examples/` 检查。`sol-*` 为参考实现（头注释已注明），做完再看。
