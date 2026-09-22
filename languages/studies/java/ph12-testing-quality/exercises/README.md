# ph12 单元测试与工程质量 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ JUnit Jupiter 5.10.1。本机 Maven 实测用 `mvn -o` 离线模式（沙箱禁止写默认本地仓库 `~/.m2`，依赖来自本地缓存 `/tmp/m2clone`）；正常联网环境直接 `mvn clean test` 即可。
> 五题与 Roadmap「ph12 单元测试与工程质量阶段」练习小节一一对应：工具类测试 / Service 测试 / Mock 数据库依赖 / Testcontainers 测数据库，并补一题「参数化测试 + 覆盖率」（与学习内容里的参数化测试、覆盖率和静态检查对应）。sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看；sol 文件是「源代码 + 注释里的完整 pom 与测试类」，建工程时按注释把 pom 与测试类写入自己的工程。
> 练习 3 需要 Mockito（pom 参考 [../examples/ex03-mockito/pom.xml](../examples/ex03-mockito/pom.xml) 的「离线版本仲裁」注释），练习 5 需要 hsqldb（纯 Java 内存库，离线可用）。

## 练习 1：工具类测试（★）

**目标**：给纯函数工具类写完整 JUnit 5 测试，覆盖正常路径、边界值与错误路径——纯函数是单元测试最容易入门的对象。
**要求**：

- 实现 `com.example.NumberUtils.isLeapYear(int year)`：公历闰年规则（能被 4 整除且不能被 100 整除，或能被 400 整除）；`year <= 0` 抛 `IllegalArgumentException`
- 写 JUnit 5 测试，至少覆盖：普通闰年（2024）、普通平年（2023）、整百年非闰（1900）、400 的倍数闰年（2000）、边界（year=1）、负数抛异常
- 用 `assertTrue/assertFalse/assertThrows`，每个测试一个行为

**验收**：`mvn test` 全部通过，`Tests run ≥ 6`，报告里无 skipped。

## 练习 2：Service 测试 + 手工替身（★★）

**目标**：不引入任何 mock 框架，用手写 fake 给带依赖的业务服务写测试——理解「替身」的本质是接口实现。
**要求**：

- 定义 `UserRepository` 接口（`findById` / `existsByEmail` / `save`）与 `UserService`（`greeting` 用户存在返回问候、不存在抛 `IllegalArgumentException`；`register` 邮箱重复拒绝、否则落库），依赖构造器注入
- 手写 `FakeUserRepository implements UserRepository`（内存 `Map` 实现），**测试代码禁止出现 `org.mockito` 导入**
- 测试覆盖：问候正常路径 / 问候错误路径 / 注册成功后可查回（基于 fake 内部状态断言）/ 重复邮箱拒绝

**验收**：`mvn test` 全部通过；`grep -r mockito src/test` 无结果。

## 练习 3：Mockito mock 数据库依赖（★★★）

**目标**：用 Mockito 生成依赖替身，隔离外部世界并验证交互——mock 与手工 fake 的互补关系。
**要求**：

- 复用练习 2 的 `UserRepository` / `UserService`（或主文档 3.3 同款），引入 `mockito-core` + `mockito-junit-jupiter`（版本与「离线版本仲裁」见 [../examples/ex03-mockito/pom.xml](../examples/ex03-mockito/pom.xml)）
- `@ExtendWith(MockitoExtension.class)` + `@Mock`，至少 5 个测试：`when().thenReturn()` 正常值、`thenReturn(Optional.empty())` 错误路径、`thenThrow()` 模拟数据库故障、`verify(repo, never()).save(...)` 验证「没有发生」、`argThat(...)` 参数匹配

**验收**：`mvn test` 全部通过；写出至少一个 `never()` 用例与一个 `thenThrow()` 用例，并能在注释里说明「为什么用 mock 而不是连真库」。

## 练习 4：参数化测试 + 覆盖率（★★★）

**目标**：用 `@ParameterizedTest` 把一组输入一组预期写成一张表，并挂 JaCoCo 生成覆盖率报告、读懂三类数字。
**要求**：

- 在 练习 1 的 `NumberUtils` 上新增 `daysInFebruary(int year)`（闰年 29 天否则 28）
- 用 `@CsvSource` 把练习 1 的闰年用例写成一行一组；用 `@MethodSource` 覆盖非法年份（0、-4、-100）的异常路径
- **故意不测 `daysInFebruary`**，pom 挂 jacoco-maven-plugin 0.8.11（`prepare-agent` + `report` 两个 execution，见 examples/ex06-jacoco-coverage/pom.xml）
- 跑完打开 `target/site/jacoco/index.html`，记下指令/行/方法三类覆盖率数字

**验收**：`mvn test` 全部通过且报告生成；能说出报告里 `NumberUtils.daysInFebruary` 为什么是红色（未覆盖），以及「指令覆盖率 = 测到的指令 ÷ 全部指令」的含义。

## 练习 5：集成测试测数据库（★★）

**目标**：用 HSQLDB 内存数据库做一次真实的 JDBC 集成测试——验证「代码 + SQL 与真实数据库引擎协作」；对照 Testcontainers 理解两条集成测试路线的取舍。
**要求**：

- 实现 `JdbcUserRepository implements UserRepository`（JDBC + `PreparedStatement`，构造器接收 `Connection`），SQL 用标准 HSQLDB 可执行的建表语句
- 测试类：`@BeforeAll` 连 `jdbc:hsqldb:mem:userdb` 并建表、`@AfterAll` 关连接、`@BeforeEach` 清表；覆盖保存后查回、查不存在返回空、邮箱存在判定、重复邮箱入库抛异常（UNIQUE 约束）
- hsqldb 依赖 `org.hsqldb:hsqldb:2.5.0`（scope `test` 即可；HSQLDB 通过 JDBC 服务发现机制自动注册驱动）
- 读完 [../examples/ex07-testcontainers.md](../examples/ex07-testcontainers.md)，在 sol 文件头写出「内存库 vs Testcontainers 各适合什么场景」

**验收**：`mvn test` 全部通过，`Tests run ≥ 4`；能说清内存库与 Testcontainers 的差异（启动速度、与生产库行为一致性、对 Docker 的依赖）。

完成 5 题后再对照 sol-* 复盘。sol 文件头是验证块（环境/命令/实测数字），sol 内的 pom 与测试类在注释里——先自己想清楚再对注释。
