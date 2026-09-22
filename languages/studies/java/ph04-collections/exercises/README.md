# ph04 集合框架 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同，如 `sol-01-student-list.java` 的类名是 `StudentList`），编译用文件名、运行用类名，如 `javac sol-01-student-list.java` + `java StudentList`。

## 练习 1：List 管理学生（★）

**目标**：掌握 List 的增删改查、按值查找与排序，学会在遍历中安全删除元素。
**要求**：
- 初始名单 `["Alice", "Bob", "Charlie", "David"]`（`List.of` 返回的是不可变列表，直接 add/remove 会抛异常，需包一层 `new ArrayList<>(...)`）
- 依次完成：添加 `"Eve"` → 移除 `"Bob"` → 打印 `indexOf("David")` → 按字母自然排序 → 删除所有以 `"C"` 开头的学生 → 打印最终名单
- 删除必须用 `removeIf` 完成——在 for-each 循环里直接 `remove` 会抛 ConcurrentModificationException
**验收**：全程无异常；`indexOf("David")` 输出 `2`；排序后、删除 C 开头前的名单为 `[Alice, Charlie, David, Eve]`；最终名单为 `[Alice, David, Eve]`。

## 练习 2：Map 统计词频（★★）

**目标**：掌握 HashMap 的 `getOrDefault` 计数、entrySet 遍历与「找最高频词」。
**要求**：
- 输入文本 `"Apple banana Apple orange banana apple apple"`，按空格切词
- 统计前先 `toLowerCase()` 归一化，不区分大小写
- 累加必须用 `getOrDefault`（禁止用 `containsKey` + `put` 两次查询）
- 输出每个词及出现次数；再输出出现次数最多的词，并列时取字典序最小
**验收**：`apple` 计 4 次、`banana` 计 2 次、`orange` 计 1 次；最高频词为 `apple`。

## 练习 3：Set 去重（★★）

**目标**：掌握三种 Set 实现的差异——HashSet（无顺序）、LinkedHashSet（保插入序）、TreeSet（自然排序）。
**要求**：
- 输入数组 `[5, 3, 1, 5, 2, 3, 4, 1]`，分别用 `LinkedHashSet` 和 `TreeSet` 去重并打印
- 构造集合 `{1, 2, 3, 10, 11}`，用 `HashSet` 的 `retainAll` 求交集并打印（注意 `retainAll` 会就地修改调用者，先拷贝一份）
**验收**：LinkedHashSet 输出 `[5, 3, 1, 2, 4]`；TreeSet 输出 `[1, 2, 3, 4, 5]`；交集输出 `[1, 2, 3]`。

## 练习 4：PriorityQueue 任务调度（★★★）

**目标**：掌握 PriorityQueue 的最小堆默认、反转比较器变最大堆、自定义比较器，理解「遍历无序、poll 有序」。
**要求**：
- 定义嵌套类 `Task`（字段 `name`、`priority`，priority 越小越紧急），用 `Comparator.comparingInt` 构造最小堆
- offer 四个任务：紧急修复(1)、功能开发(2)、代码审查(3)、文档更新(4)，循环 `poll()` 打印处理顺序
- 再用 `Comparator.reverseOrder()` 构造最大堆，对 `[3, 1, 4, 1, 5, 9, 2, 6]` 依次 `poll()` 出前 3 个最大值
- 额外验证：对最小堆直接 for-each 打印，观察它**不是**有序的——堆只保证父节点小于子节点，不保证兄弟间顺序
**验收**：任务处理顺序为 `紧急修复 → 功能开发 → 代码审查 → 文档更新`；TopK 前 3 个最大值为 `9, 6, 5`。
