# ph02 阶段项目：学生管理系统

## 需求

对应 Roadmap「面向对象 OOP 阶段」推荐项目第一个。实现一个内存版学生管理系统：`Student` 封装学生信息与成绩，`CourseClass`（班级）组合一组学生并提供统计，`StudentRegistry` 提供增删查，`Main` 演示完整流程。综合运用封装、继承/组合、getter/setter 校验、`record` 成绩快照。

## 功能清单

- [ ] `Student`：private 字段（id/name/age），构造初始化；`addScore` 校验 0~100；成绩列表不可被外部修改
- [ ] `record ScoreEntry(String subject, double score)`：不可变成绩快照
- [ ] `CourseClass`：组合一组学生；`averageScore()`、`topStudent()` 统计
- [ ] `StudentRegistry`：按 id 注册/查找/删除学生，重复 id 拒绝注册
- [ ] `Main`：注册 3 名学生、录入成绩、打印班级统计与第一名

## 验收标准

- `javac *.java` 编译零警告（OpenJDK 17.0.16）
- 重复注册相同 id 被拒绝并提示
- `setScore` 越界（>100）抛 `IllegalArgumentException`
- 班级平均分计算正确（如 92.5、85.0、78.0 平均 85.17 附近）
- `topStudent()` 返回平均分最高的学生
- 返回的成绩列表在外部 `add` 会抛 `UnsupportedOperationException`（不可变视图）

## 扩展方向（可选）

- 把 `StudentRegistry` 持久化到文件/数据库 —— 属于 ph04 集合与 IO / ph07 JDBC 阶段
- 用 `Map<String, Student>` 重写索引并讨论时间复杂度 —— 属于 ph04 集合阶段
- 给学生加 `Comparator` 排序输出 —— 属于 ph04 集合阶段

## 验证环境

OpenJDK 17.0.16。编译：`javac *.java`；运行：`java Main`。已在本环境验证。
