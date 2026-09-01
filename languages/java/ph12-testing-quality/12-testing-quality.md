# Java 单元测试与工程质量阶段

> 面向企业级后端、微服务方向，本阶段把「测试」从随手写几行 assertEquals 升级为可信的质量证据——掌握 JUnit 5 / Mockito / AssertJ 三大工具，会写单元测试与集成测试，会用参数化测试把用例收敛成事实表，用覆盖率与静态检查发现风险盲区。

## 1. 概述

ph11 构建工具阶段让 JaCoCo 覆盖率报告在 `mvn test` 后自动生成，但「报告上的数字」从哪来、怎么写测试才能让数字变绿、mock 与 fake 有什么区别、集成测试怎么测数据库——这些是 ph11 明确留给本阶段的问题。本阶段的目标（roadmap 第 12 节）：**写出可靠、可维护的 Java 工程代码**——用 JUnit 5 断言与生命周期搭测试骨架，用参数化测试把「一组输入一组预期」收敛成表，用 Mockito / 手工替身隔离外部依赖，用 HSQLDB / Testcontainers 验证真实组件协作，最后用 JaCoCo 覆盖率与 `javac -Xlint` 静态检查兜底。**测试应覆盖正常路径和错误路径**，**Mock 用于隔离外部依赖**，**集成测试验证真实组件协作**，**覆盖率不是唯一质量指标**——这四个「必会概念」贯穿全章。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 测试框架 | JUnit 5（Jupiter）：`@Test` / 生命周期注解 / 断言族；与 JUnit 4 的差异 |
| 参数化测试 | `@ParameterizedTest` + `@ValueSource` / `@NullAndEmptySource` / `@CsvSource` / `@MethodSource` |
| 测试替身 | 手工 stub/fake/spy（零框架）、Mockito mock / stub / verify / 参数匹配 |
| 断言风格 | JUnit 断言 vs AssertJ 流式断言（链式、异常断言） |
| 集成测试 | HSQLDB 内存库（本机实测）、Testcontainers 真容器（概念，未在本环境验证） |
| 质量度量 | JaCoCo 覆盖率（指令/行/分支/方法/类）、`javac -Xlint` 静态检查、覆盖率门槛 |
| 测试设计 | 正常路径 + 错误路径 + 边界值、测试方法命名、测试隔离 |

这个阶段只涉及**测试的编写与设计**（JUnit 5 / Mockito / AssertJ / 参数化 / 替身 / 覆盖率 / 静态检查），**不涉及数据库编程本身**（JDBC 细节、连接池、事务、索引、ORM——ph13 数据库阶段的内容，本阶段只借最小 JDBC 代码演示集成测试怎么测数据库）、**不涉及 Web 层与框架测试**（HTTP、Servlet、Spring MVC 的 Controller/API 测试——ph14/ph15 阶段的内容）、**不涉及 CI/CD 流水线里的质量门禁落地**（Jenkins、GitHub Actions 上的测试与覆盖率门槛——ph19 DevOps 与部署阶段的内容）。本阶段承接 ph11——`mvn test` 管「跑不跑测试」，本阶段管「测试怎么写才可信」。

## 2. 来源与演变

单元测试框架的历史就是 Java 测试思想的演进史。**JUnit** 由 Kent Beck 与 Erich Gamma 于 1997 年创建（源于 Smalltalk 的 SUnit），奠定「测试方法 + 断言 + 运行器」的基本形态：JUnit 3（2000 年前后）靠**反射 + 方法名约定**发现测试（方法名必须以 `test` 开头、必须继承 `TestCase`），JUnit 4（2006）用**注解**革命——`@Test`、`@Before`、`@After` 取代继承与命名约定，并借 Hamcrest 匹配器引入可读断言；**JUnit 5**（2017 年发布 5.0）是整个平台的彻底重写，拆成**三组件架构**：`JUnit Platform`（测试引擎 SPI，谁都能接入）、`Jupiter`（新注解/断言/扩展模型）、`Vintage`（兼容跑老 JUnit 4 测试）——它是首个「为 JVM 语言生态设计」的测试平台，不只服务 Java。设计哲学一句话加粗：**测试框架的职责是「让写测试变得廉价、让失败信息变得可读」**。

替身与断言工具并行演进。**Mockito** 2007 年由 Szczepan Faber 创建（受 EasyMock 启发但 API 更友好），基于 **ByteBuddy 字节码生成**在运行时动态创建接口/类的替身；3.x（2019）要求 Java 8+，5.x（2022）要求 Java 11+ 并默认 inline mock maker。**AssertJ** 2013 年从 FEST Assert（2007）fork 而来，主打**流式断言**：`assertThat(actual).isEqualTo(expected)` 一条链写到底，失败信息自动带上实际值与预期值的差异。**Testcontainers** 2015 年由 Richard North 开源，2019 年并入 Docker 官方生态，2021 年推出商业化托管——它的主张是「用真实容器测真实依赖」：测试时起一个 MySQL/PostgreSQL/Redis 容器，测完销毁，解决「内存库与生产库行为不一致」这个集成测试的老大难。

覆盖率与静态检查的历史更长：**覆盖率（coverage）** 概念源于 1970 年代软件度量研究，Java 侧 **EclEmma**（2005）→ **JaCoCo**（2009 独立）成为事实标准，按**指令 / 分支 / 行 / 方法 / 类**五个粒度统计「测到的 ÷ 全部」；静态检查则从 **Checkstyle**（2001，代码风格）、**FindBugs**（2006，缺陷模式，2016 fork 为 SpotBugs）到编译器自带 **`javac -Xlint`**（JDK 1.5 起，按警告类别开关）。

| 版本/里程碑 | 年份 | 主要变化 |
|-----------|------|---------|
| JUnit 3.8 | 2000 | 反射 + `testXxx` 命名约定发现测试，必须继承 TestCase |
| JUnit 4.13 | 2006–2021 | 注解化 `@Test`/`@Before`，断言 + 异常 + 超时，Hamcrest 匹配器 |
| JUnit 5.0 / 5.10 | 2017 / 2023 | Platform + Jupiter + Vintage 三组件，参数化/嵌套/动态测试，扩展模型 |
| Mockito 5.x | 2022 | Java 11+，ByteBuddy 生成替身，inline mock maker |
| AssertJ 3.x | 2013–2023 | 流式断言 `assertThat(...).isEqualTo(...)`，异常与集合断言丰富 |
| Testcontainers 1.19 | 2015–2023 | Docker 容器化依赖，JUnit 5 扩展，MySQL/PostgreSQL/Redis 等模块 |
| JaCoCo 0.8.11 | 2009–2023 | 字节码插桩统计五类覆盖率，支持 Java 17/21 |
| javac -Xlint | 2004 起 | 编译器内置静态检查，按类别开关（unchecked/deprecation/serial/fallthrough…） |

本文示例以 **OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1** 为基线（验证工具链：`javac -version` → 17.0.18、`mvn -version` → 3.9.12；配套 **Mockito 5.11.0、AssertJ 3.25.3、JaCoCo 0.8.11、HSQLDB 2.5.0** 全部本机实测通过；**Testcontainers 1.19.1 因沙箱无 Docker 守护进程（`/var/run/docker.sock` 不存在）未实跑**，只做概念讲解，见 3.5 与第 6 章）。本机 Maven 用 `mvn -o` 离线模式，依赖/插件取自本地仓库缓存（沙箱禁止写 `~/.m2`，用 `-Dmaven.repo.local=/tmp/m2clone` 指向可写目录的克隆；正常联网环境直接 `mvn test` 即可）。测试语法（注解、断言、参数化、替身 API）自 JUnit 5.0 定型以来高度稳定，5.10 上写的东西可直接迁移到 5.12/6.0——这是整个 Java 学习路线中最稳定、投入产出比最高的知识之一。

## 3. 语法与参数

### 3.1 JUnit 5 基础：注解、断言与生命周期

JUnit 5（Jupiter）的核心是**注解驱动的测试方法**：`@Test` 标记测试方法，断言从 `org.junit.jupiter.api.Assertions` 静态导入。生命周期注解控制测试的初始化与清理，执行顺序是固定的（实测输出见 examples/ex01）：

| 注解 | 执行时机 | 是否 static | 典型用途 |
|------|---------|------------|---------|
| `@BeforeAll` | 整个测试类执行前，一次 | 必须 static | 建连接池、启动测试环境 |
| `@AfterAll` | 整个测试类执行后，一次 | 必须 static | 关连接、清理环境 |
| `@BeforeEach` | 每个测试方法前 | 否 | 重建被测对象（测试隔离的关键） |
| `@AfterEach` | 每个测试方法后 | 否 | 清理测试产生的数据 |
| `@Test` | 被标记的方法作为测试执行 | 否 | 一个测试一个行为 |
| `@DisplayName` | 测试的展示名（中文亦可） | — | 让失败报告读起来像需求描述 |

```java
// examples/ex01-junit5-basic/ —— JUnit 5 断言（正常+错误路径）与生命周期（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1，测试命令：mvn test（已验证）
@BeforeEach
void setUp() {
    calculator = new Calculator();   // 每个测试从干净状态开始
}

@Test
@DisplayName("错误路径：除数为 0 抛 IllegalArgumentException")
void divideByZeroThrows() {
    IllegalArgumentException ex = assertThrows(
            IllegalArgumentException.class,
            () -> calculator.divide(10, 0));   // 传的是「执行动作」lambda，不是结果
    assertEquals("除数不能为 0", ex.getMessage());
}

@Test
@DisplayName("assertAll 聚合多个断言：失败时全部报告，而不是停在第一个")
void multipleAssertions() {
    assertAll("四则运算",
            () -> assertEquals(4, calculator.add(2, 2)),
            () -> assertEquals(0, calculator.subtract(2, 2)),
            () -> assertEquals(2, calculator.divide(6, 3)));
}
```

**断言族与关键语义**：

- `assertEquals(expected, actual)`：对象相等用 `equals`——**引用类型不要用 `assertSame` 冒充相等断言**（record 自带 `equals`，测试里大量用它）
- `assertThrows(类型, lambda)`：断言抛异常并拿到异常对象继续断言消息——**必须传「执行动作」而不是调用结果**（写成 `calculator.divide(10, 0)` 会先执行再断言，永远失败）
- `assertAll(描述, lambda...)`：聚合多个断言，全部执行完再统一报告——避免「第一个断言失败就看不到后面的失败」
- 每个测试只验证一个行为，方法名 `divideByZeroThrows` 读起来像句子——这是测试可维护性的第一道门槛

> 测试报告（surefire 输出 `Tests run: 3`）、`mvn test` 生命周期、JaCoCo 挂在生命周期上的机制，属于 ph11 构建工具阶段的内容，这里把 `mvn test` 当作「跑全部测试」的既定命令用。

### 3.2 参数化测试：一组输入一组预期

「同一个断言逻辑，换 N 组输入」是测试里最常见的重复。JUnit 5 的 `@ParameterizedTest` 把这件事收敛成一张表：一个方法 + N 组数据 = N 次独立执行，任一组失败只报那一组。

| 数据源注解 | 提供什么 | 适用 |
|-----------|---------|------|
| `@ValueSource(strings/ints/...)` | 一组同类型值 | 一个参数、无预期值 |
| `@NullSource` / `@EmptySource` / `@NullAndEmptySource` | null / 空串 / 两者 | 补上普通 ValueSource 传不了的 null |
| `@CsvSource` | 逗号分隔的多列，一行一组 | 输入 + 预期、边界值表 |
| `@MethodSource` | 工厂方法返回 `Stream<Arguments>` | 复杂输入/预期对、需要代码生成数据 |

```java
// examples/ex02-parameterized/ —— 参数化测试四类数据源（完整版见 examples/，实测 Tests run: 14）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1，测试命令：mvn test（已验证）
@ParameterizedTest
@NullAndEmptySource
@ValueSource(strings = {"   ", "\t\n"})
void isBlank_shouldReturnTrue(String input) {
    assertTrue(StringUtils.isBlank(input), () -> "isBlank(" + input + ") 应为 true");
}

@ParameterizedTest
@CsvSource({
        "abc,cba",
        "hello,olleh",
        "a,a",
        "'',''"      // 实测（5.10.1）：裸空单元格→null，引号包裹 ''→空串
})
void reverse_basic(String input, String expected) {
    assertEquals(expected, StringUtils.reverse(input));
}

@ParameterizedTest
@MethodSource("reverseCases")
void reverse_fromMethodSource(String input, String expected) {
    assertEquals(expected, StringUtils.reverse(input));
}

static Stream<Arguments> reverseCases() {
    return Stream.of(
            Arguments.of("Java", "avaJ"),
            Arguments.of("", ""),
            Arguments.of(null, ""));   // null 视为空串
}
```

- **surefire 把每次参数执行计为一个测试**：上例 4 个参数化方法 × 3/3/4/4 组数据 = 实测 `Tests run: 14`
- **数据语义要实测确认**：`@CsvSource` 中**裸空单元格 → null**、**引号包裹 `''` → 空串 `""`**——首个版本写成 `"'',"`（第二格裸空）预期 null 而失败，改为 `"'',''"` 通过；这是「参数化测试的数据语义必须用真实验证」的教材
- 参数化测试与覆盖率的关系：6 组 `CsvSource` 数据覆盖 `isLeapYear` 的全部分支，等于 6 个手工测试方法的覆盖率效果——**表比复制粘贴更不容易漏分支**（练习 4 实测）

### 3.3 测试替身：手工 stub/fake 与 Mockito

被测对象常依赖数据库、网络、时钟等外部世界。**测试替身（Test Double）**把外部世界换成可控的假货，让测试快、确定、可覆盖错误路径。替身家族五个成员（Gerard Meszaros 的 xUnit Test Patterns 分类）：

| 替身 | 是什么 | 验证方式 | 本阶段落点 |
|------|--------|---------|-----------|
| Dummy | 只凑参数、从不被调用 | — | 传一个占位对象 |
| Stub | 固定返回预设值 | 状态验证（返回值） | 手工 `FixedClock` / Mockito `when().thenReturn()` |
| Fake | 有真实行为的简化实现 | 状态验证（内部状态） | 手工 `FakeUserRepository`（内存 Map） |
| Spy | 包一层记录调用 | 交互验证（调没调、调几次） | 手工 `CountingClock` / Mockito `spy()` |
| Mock | 预设行为 + 记录交互 | 交互验证 + 状态验证 | Mockito `mock()` |

**手工替身（零框架，永远可实测）**——替身的本质是「接口实现」，手写一个类即可：

```java
// examples/ex04-handmade-stub/ —— 手工 stub/spy：Clock 接口内嵌的两个替身（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1，测试命令：mvn test（已验证）
// FixedClock / CountingClock 实际定义在 Clock 接口内部作为嵌套类（测试里 import com.example.Clock.FixedClock）
final class FixedClock implements Clock {          // stub：固定时间
    private final Instant fixed;
    FixedClock(Instant fixed) { this.fixed = fixed; }
    @Override public Instant now() { return fixed; }
}

final class CountingClock implements Clock {      // spy：记录调用次数
    private int calls;
    @Override public Instant now() { calls++; return Instant.parse("2026-09-01T10:00:00Z"); }
    int calls() { return calls; }
}

@Test
void boundary_exactNineIsOpen() {
    assertTrue(new OpeningHours(new FixedClock(at(9))).isOpen());
}

@Test
void now_isCalledExactlyOncePerCheck() {
    CountingClock counting = new CountingClock();
    new OpeningHours(counting).isOpen();
    assertEquals(1, counting.calls(), "每次判定应恰好调用一次 now()");
}
```

> 手工替身适合「行为简单、数量少」的依赖（时钟、单方法接口）；依赖复杂（几十个方法、多层调用）时手工实现会膨胀，交给 Mockito——**Mockito 替身属于本阶段 3.3 的另一个小节，这里先建立「替身 = 接口实现」的心智模型**。

**Mockito（行为验证）**——用 `@ExtendWith(MockitoExtension.class)` + `@Mock` 生成替身，`when().thenReturn()` 规定返回值（stub），`verify()` 验证交互：

```java
// examples/ex03-mockito/ —— Mockito：stub + verify + never + argThat + thenThrow（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Mockito 5.11.0，测试命令：mvn test（已验证）
@ExtendWith(MockitoExtension.class)
class UserServiceMockitoTest {

    @Mock
    private UserRepository repo;          // Mockito 生成 UserRepository 的替身

    private UserService service;

    @BeforeEach
    void setUp() {
        service = new UserService(repo);  // 构造器注入 mock —— 被测服务与真实数据库完全隔离
    }

    @Test
    void greeting_returnsHello_whenUserExists() {
        when(repo.findById(1L)).thenReturn(Optional.of(new User(1L, "mosslau", "m@x.com")));

        assertEquals("Hello, mosslau!", service.greeting(1L));

        verify(repo).findById(1L);        // 验证交互确实发生了（且只发生一次）
    }

    @Test
    void register_rejectsDuplicateEmail() {
        when(repo.existsByEmail("dup@x.com")).thenReturn(true);

        assertThrows(IllegalArgumentException.class,
                () -> service.register(new User(2L, "dup", "dup@x.com")));

        verify(repo, never()).save(any());   // 验证「没有发生」：重复邮箱不许落库
    }

    @Test
    void repositoryFailure_isPropagated() {
        when(repo.findById(1L)).thenThrow(new RuntimeException("数据库连接失败"));

        assertThrows(RuntimeException.class, () -> service.greeting(1L));
    }
}
```

**Mockito 常用 API 速查**：

| 意图 | 写法 | 说明 |
|------|------|------|
| stub 返回值 | `when(repo.findById(1L)).thenReturn(Optional.of(user))` | 匹配到才返回 |
| stub 抛异常 | `when(repo.findById(1L)).thenThrow(new RuntimeException(...))` | 模拟外部故障 |
| 空返回值 | `when(repo.findById(99L)).thenReturn(Optional.empty())` | 错误路径 |
| 验证发生 | `verify(repo).findById(1L)` | 恰好一次 |
| 验证没发生 | `verify(repo, never()).save(any())` | 负面断言，比返回值更严格 |
| 参数匹配 | `argThat(u -> u.name().equals("new"))` / `any()` / `anyLong()` | 验证「以什么参数调用」 |

**为什么用 mock 而不是连真库**：单元测试要快（毫秒级）、要确定（无外部状态）、要能覆盖错误路径——「数据库挂掉」这种场景连真库根本复现不了。mock 与手工 fake 的分工见 5 章。

### 3.4 AssertJ：流式断言

JUnit 断言是「一个方法一个断言」，AssertJ 是「一条链多个断言」：`assertThat(实际值)` 返回一个断言对象，链式调 `isEqualTo/hasSize/extracting/...` 一路断言下去，失败信息自动打印实际值与预期的差异。断言对象按类型分（`assertThat(集合)`、`assertThat(异常动作)`、`assertThat(int)`…），IDE 自动补全提示可用的断言——**这是 AssertJ 的核心生产力：不查文档也能写对断言**。

| 对比维度 | JUnit 5 断言 | AssertJ 流式断言 |
|----------|-------------|-----------------|
| 写法 | `assertEquals(3, cart.total())` | `assertThat(cart.total()).isEqualTo(3)` |
| 多属性 | `assertAll` 包 lambda | 一条链 `.hasSize(2).extracting(...).containsExactly(...)` |
| 异常断言 | `assertThrows` + 再断言 | `assertThatThrownBy(() -> ...).isInstanceOf(...).hasMessageContaining(...)` |
| 失败信息 | 基础 | 自动带实际值/预期值差异、集合元素对比 |

```java
// examples/ex05-assertj/ —— AssertJ 流式断言（完整版见 examples/，实测 Tests run: 5）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + AssertJ 3.25.3，测试命令：mvn test（已验证）
assertThat(cart.items())
        .hasSize(2)
        .extracting(Item::name)
        .containsExactly("Java 编程思想", "Effective Java");

assertThatThrownBy(() -> cart.items().add(new Item("x", 1)))
        .isInstanceOf(UnsupportedOperationException.class);

assertThatThrownBy(() -> cart.add(new Item("", 10)))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("商品非法");
```

> 本阶段 JUnit 断言与 AssertJ 并行出现（示例 1/2/3 用 JUnit 断言、示例 5 与项目用 AssertJ）——**两者不冲突**：JUnit 断言是语言内置的保底，AssertJ 是让断言更可读的增强；真实工程两者混用很常见，团队定一个偏好即可。

### 3.5 集成测试：内存库与 Testcontainers

单元测试隔离了外部依赖，集成测试则**验证真实组件协作**——代码 + SQL 与真实数据库引擎是否真的能一起工作。两条路线各有取舍：

| 路线 | 是什么 | 优点 | 代价 | 本阶段验证状态 |
|------|--------|------|------|--------------|
| 内存数据库（HSQLDB/H2） | 纯 Java 嵌入式库，跑在测试 JVM 里 | 秒级启动、零 Docker、离线可用 | 与生产 MySQL/PostgreSQL 行为不完全一致 | ✅ 本机实测（examples/ex07 替代方案、exercises 练习 5、project/） |
| Testcontainers | Docker 起真实 MySQL/Postgres/Redis 容器 | 行为与生产一致，可测数据库专有特性 | 需要 Docker 守护进程、首次拉镜像慢 | ⚠️ 未在本环境验证（沙箱无 Docker） |

**内存库集成测试**（HSQLDB，`jdbc:hsqldb:mem:userdb`）——`@BeforeAll` 连库建表、`@AfterAll` 关连接、`@BeforeEach` 清表，测试间互不污染：

```java
// project/src/test/java/.../JdbcUserRepositoryTest.java —— HSQLDB 集成测试（完整工程见 project/）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + HSQLDB 2.5.0，测试命令：mvn test（已验证）
@BeforeAll
static void openDb() throws Exception {
    conn = DriverManager.getConnection("jdbc:hsqldb:mem:userdb", "sa", "");
    try (Statement st = conn.createStatement()) {
        st.execute("CREATE TABLE users ("
                + "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
                + "name VARCHAR(64) NOT NULL, "
                + "email VARCHAR(128) NOT NULL UNIQUE)");
    }
}

@Test
void save_assignsDatabaseGeneratedId() {
    User saved = repo.save(new User(0L, "mosslau", "m@x.com"));

    assertThat(saved.id()).isPositive();   // 主键由数据库自增列生成
    assertThat(saved.name()).isEqualTo("mosslau");
}
```

> 这里只借「连真实引擎跑 SQL」这一件事演示集成测试怎么写；**JDBC 细节、连接池、事务、索引、ORM 属于 ph13 数据库阶段**，本阶段不展开。

**Testcontainers**（真实容器，本沙箱无 Docker 未实跑，标准用法片段见 [`examples/ex07-testcontainers.md`](./examples/ex07-testcontainers.md)）：`@Testcontainers` 扩展管理容器生命周期，`@Container` 字段声明容器，`getJdbcUrl()` 等容器对象方法提供连接信息（随机端口避免冲突），测试结束自动 `stop` 清理。适合验证生产数据库专有行为（如 MySQL 的 `ON DUPLICATE KEY UPDATE`、JSON 类型、事务隔离级别）。

### 3.6 覆盖率与静态检查：JaCoCo 与 javac -Xlint

**JaCoCo 覆盖率**：`mvn test` 时 `prepare-agent` 注入 javaagent 记录执行数据，`report` 生成 `target/site/jacoco/` 报告。五类粒度（实测数字见 examples/ex06 与 project/）：

| 粒度 | 含义 | ex06 实测（只测 add 不测 divide） |
|------|------|--------------------------------|
| 指令 INSTRUCTION | 测到的字节码指令 ÷ 全部 | **7/11（63.6%）** |
| 行 LINE | 测到的源码行 ÷ 全部 | 2/3 |
| 方法 METHOD | 至少执行过的方法 ÷ 全部 | 2/3 |
| 分支 BRANCH | 条件分支两个方向都走到 ÷ 全部 | 0/0（该例无分支） |
| 类 CLASS | 被加载执行的类 ÷ 全部 | 1/1 |

**覆盖率 = 测到的 ÷ 全部**：只测 `add` 不测 `divide`，`divide` 的指令就是红色缺口。project/ 全量测试后实测：指令 92%、行 92%、方法 100%、分支 83%——**分支最低，因为错误路径（`SQLException → RuntimeException` 包装、email 为 null 的短路）没测到**，这是「覆盖率不是唯一质量指标」的活例：数字好看不等于错误路径安全，测试设计才是源头。

**`javac -Xlint` 静态检查**：编译器自带的按类别开关的警告（实测，`javac -Xlint:all`）：

```bash
# 实测：故意制造裸类型/废弃构造器/序列化无 serialVersionUID/switch 穿透的样例
javac -Xlint:all LintDemo.java
# 实测输出 6 个警告：[rawtypes] ×2、[unchecked]、[removal]（Integer(int) 已废弃待删）、
#               [serial]（可序列化类没有 serialVersionUID）、[fallthrough]（switch 缺 break）
```

常用类别：`unchecked`（裸类型/未检查转换）、`deprecation`/`removal`（用了废弃 API）、`serial`（Serializable 缺 serialVersionUID）、`fallthrough`（switch 穿透）、`rawtypes`（裸泛型）。Maven 侧可在 maven-compiler-plugin 配置 `<compilerArgs><arg>-Xlint:all</arg></compilerArgs>` 让每次编译都带检查。javac 的 `-Xlint` 与 Checkstyle/SpotBugs 的分工：javac 查语言级问题、Checkstyle 查风格、SpotBugs 查缺陷模式——三者在 ph11 3.8 已介绍，本阶段把 `-Xlint` 实测落地。

### 3.7 高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| `assertThrows` 里直接写调用结果 | 测试先执行、异常抛到断言外，永远红 | 传 lambda `() -> obj.method()` |
| 引用类型用 `assertSame` 断言内容 | 两个 record 内容相同但引用不同，假失败 | 用 `assertEquals`（走 `equals`） |
| 参数化测试数据语义想当然 | `@CsvSource` 空单元格是 null 不是空串，边界用例假失败 | 实测确认数据语义（3.2 教材案例） |
| mock 了不该 mock 的（如自己类） | 测试与被测实现耦合，重构就碎 | 只 mock 接口/外部依赖；内部逻辑用真实对象 |
| 测试依赖执行顺序/共享状态 | 单独跑绿、一起跑红 | `@BeforeEach` 重建被测对象，测试间零共享 |
| 测试里 `Thread.sleep` 等真实时间 | 慢 + 随机失败 | 注入 `Clock` 接口（3.3 手工替身） |
| 集成测试类名用 `*IT` | surefire 默认不跑 `*IT`，静默跳过 | 用 `*Test` 后缀；`*IT` 是 failsafe（ph11）的约定 |
| 时间相关代码用系统默认时区 | 换时区机器测试结果不同 | 显式固定时区（examples/ex04 的教训） |
| 覆盖率 100% 就以为安全 | 分支 83% 但错误路径全裸奔 | 报告按分支粒度看，错误路径单独立测试 |

## 4. 底层原理

### 4.1 JUnit 5 三组件架构与测试发现

JUnit 5 不是「一个 jar」，而是三个组件协同：**JUnit Platform** 定义测试引擎 SPI（`TestEngine`）与启动器（Launcher），**Jupiter** 是平台的默认引擎（实现 `@Test`/断言/扩展），**Vintage** 是兼容引擎（让老 JUnit 4 测试能在新平台跑）。`mvn test` 时 surefire 的 JUnit Platform provider 用 Launcher 扫描 classpath，发现 `TestEngine`，Jupiter 引擎再按注解/命名规则找到测试方法执行。

```text
mvn test ──▶ surefire ──▶ JUnit Platform Launcher ──▶ TestEngine SPI
                                            │
                          ┌─────────────────┼──────────────────┐
                          ▼                 ▼                  ▼
                     Jupiter 引擎      Vintage 引擎         其他引擎（如 TestNG）
                   @Test/断言/扩展   JUnit 4 兼容测试       生态扩展
```

- **引擎是插件点**：任何测试框架实现 `TestEngine` 接口就能接入 JUnit Platform——这是「平台」二字的含义
- **扩展模型（Extension）**：`@ExtendWith(MockitoExtension.class)` 的本质是注册一个 JUnit 扩展，在测试生命周期钩子里替 Mockito 管理 mock 的创建与校验——Mockito 与 JUnit 5 的集成就是靠扩展点，而不是 Mockito 自己改 JUnit
- **测试方法可以是包级私有**：Jupiter 不要求 public（JUnit 4 要求），测试类/方法不用写 public 修饰——这是「注解取代命名与可见性约定」的延续

### 4.2 Mockito 的字节码代理原理

Mockito 默认用 **ByteBuddy** 在运行时生成代理类：`mock(UserRepository.class)` 时，ByteBuddy 动态生成一个实现了 `UserRepository` 的新类（对接口）或 `UserRepository` 的子类（对具体类），所有方法调用被拦截，返回「智能默认值」（对象返回空 Optional/空集合，避免 NPE）；`when(...).thenReturn(...)` 记录「方法+参数 → 返回值」的桩映射，调用时查表返回。`verify(...)` 则检查调用记录。

```text
UserRepository 接口 ──ByteBuddy──▶ 生成的代理类（实现同一接口）
   所有方法调用 ──拦截──▶ 查桩映射（when 注册的）──有──▶ 返回预设值
                                    │ 无桩
                                    ▼
                              返回智能默认值（Optional.empty() 等）
   调用记录（方法、参数、次数）── verify(...) 核对
```

- **为什么 final 类/方法默认不能 mock**：final 无法被子类化、final 方法无法被覆写，字节码生成子类这条路走不通；`mockito-inline`（inline mock maker）用 JVM instrumentation 改写字节码可 mock final，但有代价（启动慢、与部分安全框架冲突）——**优先把依赖设计成接口**，别为 mock 去开 inline
- **`@ExtendWith(MockitoExtension.class)` 为什么推荐**：它让 mock 注入、`@InjectMocks` 构造注入、stub 校验（`UnnecessaryStubbingException` 抓多余 stub）都由 JUnit 扩展自动完成，漏掉它则 `@Mock` 字段是 null
- **为什么 Mockito 5.x 要求 Java 11+**：inline mock maker 与 ByteBuddy 的版本基线随 JDK 演进

### 4.3 JaCoCo 的字节码插桩

JaCoCo 不是「分析源码」，而是**在字节码里埋计数器**：`prepare-agent` 给测试 JVM 挂一个 javaagent，JVM 加载类时用 **ASM** 库改写字节码，在每条指令/分支/方法入口插入计数器指令，测试执行时计数器累加，退出时把数据写到 `target/jacoco.exec`；`report` 目标再对照 class 文件把计数映射回指令/行/方法，渲染 HTML/CSV/XML。

```text
JVM 加载 UserService.class ──javaagent(ASM 改写)──▶ 埋入计数器指令的字节码
测试执行 ──▶ 计数器累加 ──▶ 写 target/jacoco.exec（二进制执行数据）
mvn test 后 ──jacoco:report──▶ 对照 class 映射回源码 ──▶ index.html / jacoco.csv / jacoco.xml
```

- **插桩粒度是「指令」不是「行」**：指令覆盖率是 JaCoCo 最准确的粒度（行可能一行多条指令），所以报告里指令通常 ≤ 行覆盖率
- **为什么分支覆盖率常最低**：一个 `if` 产生两个分支，测试只走 true 不走 false 就是 50% 分支覆盖——错误路径最容易漏的就是这里（project/ 实测分支 83% < 指令 92%）
- **为什么测试类不进报告**：jacoco-maven-plugin 的 report 目标分析的是 `target/classes`（主类），`target/test-classes` 不在分析范围——报告统计的是「生产代码被测试覆盖的比例」

### 4.4 Testcontainers 的容器生命周期

Testcontainers 通过 **docker-java** 客户端调 Docker API：测试启动时 pull 镜像（已有则复用）→ 创建容器 → 映射随机端口 → 用 **wait strategy**（等 TCP 端口可连 + 容器日志出现就绪关键字）确认服务真正可用 → 测试代码用容器对象提供的连接信息连真实服务 → 测试结束自动 `docker stop` 并清理容器与网络。JUnit 5 扩展（`@Testcontainers`）把 start 挂在首个测试前、stop 挂在全部测试后。

```text
@Testcontainers 扩展
   ┌─ 首测前: docker-java ──▶ pull 镜像 ──▶ 起容器(随机端口) ──▶ wait strategy 就绪 ──▶ 测试连真实服务
   └─ 全部测试后: 自动 stop 容器 + 清理 ──▶ 每次测试环境从零开始，可并行、可重复
```

- **随机端口是关键设计**：容器端口映射到宿主机随机端口，CI 并行跑测试互不冲突；连接信息从容器对象拿（`getJdbcUrl()`），不硬编码
- **与内存库的本质差异**：内存库是「同一进程里的模拟」，Testcontainers 是「独立进程里的真实」——行为一致性更高，但代价是 Docker 依赖与启动耗时（秒级到十秒级）

### 4.5 覆盖率的种类与心智模型

覆盖率度量「测试执行到了多少代码」，按成本从低到高：**语句/行**（执行没执行）→ **分支**（条件两个方向走没走）→ **路径**（多条件组合，指数级，一般不测）。业界常用组合是「行 + 分支」：行覆盖告诉你「哪些代码没测过」，分支覆盖告诉你「哪些判断没走全」。心智模型就一句话：**覆盖率 = 测到的 ÷ 全部，它衡量的是「测了多少」，不衡量「测得对不对」**——一个断言都没写的「假测试」也能 100% 覆盖，所以 ph11 3.8 与 roadmap 都强调：覆盖率不是唯一质量指标，测试设计（正常/错误/边界路径）才是源头。

## 5. 使用场景

| 场景 | 涉及知识点 | 落点 |
|------|-----------|------|
| 纯函数/工具类（判空、闰年、字符串处理） | JUnit 5 断言 + 参数化测试全覆盖边界与错误路径 | examples/ex01/ex02、exercises 练习 1/4 |
| 业务服务隔离数据库/网络/时钟 | 手工替身（简单依赖）或 Mockito（复杂依赖） | examples/ex03/ex04、exercises 练习 2/3 |
| 验证「代码 + SQL」与真实引擎协作 | HSQLDB 内存库集成测试；Testcontainers 验生产专有行为 | project/、exercises 练习 5、examples/ex07 |
| 一组输入一组预期（校验规则、边界值） | 参数化测试写成事实表，加用例只加一行 | examples/ex02、project/ 的 UserValidationTest |
| 断言复杂对象/集合/异常 | AssertJ 链式断言 + 异常断言 | examples/ex05、project/ |
| 质量门禁与报告 | JaCoCo 五类覆盖率 + `javac -Xlint` 静态检查 | examples/ex06、project/ 验收标准 |
| 交付可信度 | 「测试应覆盖正常路径和错误路径」作为开发习惯 | 全阶段贯穿 |

**不适合**此阶段的事项：

- **数据库编程本身**（JDBC 细节、连接池、事务、索引、ORM）——ph13 数据库阶段（roadmap 第 13 节，目录待建）；本阶段只借最小 JDBC 演示集成测试怎么写
- **Web 层与框架测试**（HTTP、Servlet、Spring MVC 的 Controller/API 测试、MockMvc）——ph14 Web 后端开发阶段 / ph15 Spring 全家桶阶段（roadmap 第 14/15 节，目录待建）
- **CI/CD 流水线里的测试与覆盖率门槛落地**（Jenkins、GitHub Actions、质量门禁进流水线）——ph19 DevOps 与部署阶段（roadmap 第 19 节，目录待建）
- **性能/压测与模糊测试**——超出单元测试范畴，属进阶专题

## 6. 代码示例

> 本阶段示例全部**本机实测通过**（OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1；本环境沙箱禁止写默认本地仓库 `~/.m2`，Maven 用 `mvn -o` 离线模式、依赖/插件取自本地仓库缓存——正常联网环境直接 `mvn test` 即可）。ex01~ex06 为可运行 Maven 工程；**ex07 为 Testcontainers 概念文档（本沙箱无 Docker 守护进程，未实跑）**。

### 示例 1：JUnit 5 断言与生命周期（`examples/ex01-junit5-basic/`）

`@Test` / `@BeforeEach` / `@AfterEach` / `@BeforeAll` / `@AfterAll` / `@DisplayName` 全套 + 正常路径与错误路径断言 + `assertAll`，对应 3.1。实测：`mvn test` → `Tests run: 3`。

```bash
cd examples/ex01-junit5-basic && mvn test   # 实测: Tests run: 3, Failures: 0
```

### 示例 2：参数化测试（`examples/ex02-parameterized/`）

`@ValueSource` / `@NullAndEmptySource` / `@CsvSource` / `@MethodSource` 四类数据源，对应 3.2。实测：`Tests run: 14`（参数化把 4 个方法 × 3/3/4/4 组数据计为 14 次执行）。**教材坑**：`@CsvSource` 裸空单元格 → null、引号 `''` → 空串。

### 示例 3：Mockito（`examples/ex03-mockito/`）

`@ExtendWith(MockitoExtension.class)` + `@Mock` + `when().thenReturn()` + `thenThrow()` + `verify/never/argThat`，对应 3.3。实测：`Tests run: 5`。pom 中「离线版本仲裁」注释的 byte-buddy/objenesis 依赖为沙箱离线所需，正常联网环境可删除。

### 示例 4：手工替身（`examples/ex04-handmade-stub/`）

`FixedClock` stub + `CountingClock` spy + 营业时间边界测试，零框架依赖，对应 3.3。实测：`Tests run: 6`。生产代码显式固定 UTC 时区——时间相关代码的时区必须显式决定，否则测试随机器时区漂移。

### 示例 5：AssertJ 流式断言（`examples/ex05-assertj/`）

链式断言 + 异常断言 + 防御性拷贝验证，对应 3.4。实测：`Tests run: 5`。

### 示例 6：JaCoCo 覆盖率（`examples/ex06-jacoco-coverage/`）

只测 `add` 不测 `divide`，报告显示覆盖率缺口，对应 3.6。实测：`Tests run: 1`；`target/site/jacoco/jacoco.csv` 中 Calculator 指令覆盖率 **7/11（63.6%）**、行 2/3、方法 2/3——补上 divide 的测试后变 100%。

```bash
cd examples/ex06-jacoco-coverage && mvn test
open target/site/jacoco/index.html    # 实测: Calculator 行覆盖率 66%（2/3），divide 红色未覆盖
```

### 示例 7：Testcontainers 概念文档（`examples/ex07-testcontainers.md`）

Docker 容器化集成测试的 pom 依赖、标准用法片段与生命周期原理，对应 3.5。**未在本环境验证**（沙箱无 Docker 守护进程），只做概念讲解；可实测的替代路线（HSQLDB 内存库）见 project/ 的 JdbcUserRepository 集成测试。

## 7. 总结

### 关键要点

1. **JUnit 5 是注解驱动的测试平台**：`@Test` + 断言族 + 生命周期注解（`@BeforeEach` 是测试隔离的关键）；`assertThrows` 传 lambda、引用类型用 `assertEquals` 走 `equals`、`assertAll` 聚合断言
2. **参数化测试把「一组输入一组预期」收敛成表**：`@CsvSource`/`@MethodSource` 加用例只加一行，surefire 把每次参数执行计为一个测试；数据语义（空单元格=null）要实测确认
3. **替身家族：stub 定返回值、fake 有真实现、spy 记交互、mock 全都要**——手工替身永远是保底方案，Mockito 是复杂依赖的加速器
4. **Mockito 隔离外部依赖**：`when().thenReturn()` stub、`verify()/never()` 行为验证、`argThat()` 参数匹配、`thenThrow()` 模拟外部故障；`@ExtendWith(MockitoExtension.class)` 让 `@Mock` 生效
5. **集成测试验证真实组件协作**：HSQLDB 内存库秒级可测（本机实测），Testcontainers 真容器行为更贴近生产（需要 Docker，未在本环境验证）
6. **覆盖率 = 测到的 ÷ 全部**：指令/行/分支/方法/类五类粒度，分支最低最常见（错误路径漏测）；JaCoCo 报告是找缺口的地图，不是质量本身
7. **静态检查用 `javac -Xlint:all` 实测落地**：rawtypes/unchecked/removal/serial/fallthrough 六类警告当场可见
8. **测试应覆盖正常路径和错误路径**：错误路径（异常、边界、外部故障）是覆盖率缺口与线上事故的共同来源
9. **覆盖率不是唯一质量指标**：一个断言不写的假测试也能 100% 覆盖——测试设计（每个测试一个行为、命名像句子、状态可复现）才是源头

### 阶段验收清单

- [ ] 能写单元测试和集成测试：JUnit 5 断言 + 生命周期搭单元测试，HSQLDB/Testcontainers 搭集成测试（3.1/3.5、examples/ex01、project/）
- [ ] 能使用 Mock：Mockito stub/verify/never/argThat 隔离外部依赖，也能讲清与手工 fake 的分工（3.3、examples/ex03/ex04）
- [ ] 能生成覆盖率报告并读懂三类数字：JaCoCo 指令/行/分支/方法覆盖率，能指出缺口在哪、为什么（3.6、examples/ex06、exercises 练习 4）
- [ ] 能用参数化测试表达边界用例：一行一组数据，加用例只加一行（3.2、examples/ex02、exercises 练习 4）
- [ ] 能用手工替身测时间/状态相关逻辑：stub 固定时间、spy 验证调用次数（3.3、examples/ex04）
- [ ] 能写 AssertJ 链式断言与异常断言，并说明它与 JUnit 断言的取舍（3.4、examples/ex05）
- [ ] 能说清 Testcontainers 与内存库的取舍，并给出标准用法片段（3.5、examples/ex07——未在本环境验证）

### 跨语言对比：测试与工程质量

| 维度 | Java / JUnit 5 | C++ / GoogleTest | Go / testing | Python / pytest | Rust / cargo test |
|------|---------------|-----------------|--------------|-----------------|-------------------|
| 测试框架 | JUnit Platform + Jupiter（注解 + 扩展） | GoogleTest（宏 + fixture） | testing 包（`Test` 前缀函数） | pytest（`test_` 前缀函数 + fixture） | 内置测试（`#[test]` 属性） |
| 断言风格 | JUnit 断言 / AssertJ 流式 | EXPECT_EQ / ASSERT_EQ | t.Errorf / require | assert / pytest.raises | assert_eq! / should_panic |
| 参数化 | @ParameterizedTest + 数据源 | 无内置（宏生成） | 表驱动测试（循环 + 子测试） | @pytest.mark.parametrize | 无内置（宏/循环） |
| Mock | Mockito（ByteBuddy 代理） | GoogleMock | 手写接口替身（接口即契约） | unittest.mock / monkeypatch | 手写 trait 替身（trait 约束） |
| 覆盖率 | JaCoCo 五类粒度 | gcov/lcov | go test -cover | coverage.py | cargo-llvm-cov |
| 集成测试 | 内存库 / Testcontainers | 依赖注入 + 桩服务 | 无内建容器方案 | pytest-docker / testcontainers-python | 无内建容器方案 |

对比结论：五门语言的测试框架都收敛到「**轻量标记 + 断言 + 测试发现**」的同一模式，差异在参数化与替身的原生程度——Java 的参数化与 Mockito 生态最成熟，Go 与 Rust 则靠**接口/trait 约束 + 手写替身**把「依赖抽象」逼进语言设计（mock 不重要是因为接口本来就是一等公民）。覆盖率工具全语言都有，但「覆盖率不是唯一指标」的教训是共通的：**测试设计（正常/错误/边界路径）在任何语言里都比工具重要**——这是为 analysis/ 与 Tenet 合成积累的素材。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续：

- **工具类测试**（★）：给 `NumberUtils.isLeapYear` 写覆盖正常/边界/错误路径的 JUnit 5 测试
- **Service 测试 + 手工替身**（★★）：手写 `FakeUserRepository` 测 `UserService`，测试代码禁止出现 Mockito
- **Mockito mock 数据库依赖**（★★★）：Mockito 隔离存储，`when/thenReturn/thenThrow` + `verify/never/argThat` 至少 5 个用例
- **参数化测试 + 覆盖率**（★★★）：`@CsvSource`/`@MethodSource` 重写边界用例 + JaCoCo 报告，实测数字写入 sol 文件头
- **集成测试测数据库**（★★）：HSQLDB 内存库做 JDBC 集成测试，对照 Testcontainers 说出两条路线的取舍

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**带测试的用户服务**——纯 Java SE 的注册/查询/改邮箱/删除业务，四种测试手段齐上：Mockito 单元测试（8 个）、参数化校验测试（19 个）、内存仓库行为测试（6 个）、HSQLDB 集成测试（6 个），共 **39 个测试全部通过**；JaCoCo 实测指令覆盖率 **92%**、行 92%、方法 100%、分支 83%。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`mvn test` 全绿 + 能解释报告里的覆盖率缺口）

### 下一阶段

**ph13+（roadmap 第 13 节，目录待建）——本阶段是当前已建目录的最后一个阶段**：后续可深入**数据库**方向——本阶段的 HSQLDB 集成测试只写了最小 JDBC CRUD，ph13 将系统学习 JDBC 细节、连接池、事务、索引与 MyBatis/JPA/Hibernate，把「用户服务」的存储层换成真实数据库，用事务与索引设计解决真实数据问题。该阶段目录尚未创建，届时以 roadmap 第 13 节为准，本阶段不再向前引用不存在的文件。
