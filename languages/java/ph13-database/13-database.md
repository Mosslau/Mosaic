# Java 数据库阶段

> 面向企业级后端、微服务方向，本阶段把「数据」从内存里的集合升级为可持久化、可并发、可检索的数据库资产——掌握 SQL 与 JDBC 编程、事务与连接池、索引与慢查询、Redis 缓存，并理解 MyBatis / JPA / Hibernate 与 Flyway 迁移工具在真实工程中的分工。

## 1. 概述

ph12 单元测试与工程质量阶段用 HSQLDB 内存库写过最小 JDBC CRUD 集成测试，但「JDBC 到底怎么设计、事务回滚怎么保证、连接为什么必须池化、查询为什么慢、缓存放哪」这些问题是 ph12 明确留给本阶段的。本阶段的目标（roadmap 第 13 节）：**掌握 Java 操作数据库和缓存**——从 `DriverManager` 裸连与 `PreparedStatement` 参数化查询起步，理解事务边界由业务定义、连接池如何摊薄建连成本、索引如何改变查询计划，再用 Redis 缓存高频读、用 MyBatis / JPA 等 ORM 与 Flyway 迁移把数据访问工程化。**SQL 基础比 ORM 更重要**，**事务边界必须由业务定义**，**索引影响查询和写入成本**，**Redis 适合缓存和高频状态**——这四个「必会概念」贯穿全章。

| 核心维度 | 覆盖内容 |
|----------|---------|
| SQL 与 JDBC | SQL 基础（DDL/DML/约束）、`DriverManager` 连接、`Statement` vs `PreparedStatement`、参数化查询防注入、`ResultSet` 映射、自增主键回填 |
| 事务 | ACID、`setAutoCommit(false)` / `commit` / `rollback`、事务边界由业务定义、失败回滚语义实测 |
| 连接池 | 建连成本、池化心智、HikariCP 配置与实时状态、并发下小池扛大流量 |
| 索引与慢查询 | 全表扫描 vs B+ 树、`EXPLAIN PLAN FOR`、索引对查询/写入的双面影响、`addBatch` 批量造数 |
| Redis 缓存 | RESP 协议、手写客户端 vs 官方客户端（Jedis）、SET/GET/DEL/EXPIRE/TTL、Cache-Aside 缓存旁路 |
| ORM 与迁移 | MyBatis（SQL 映射）、JPA/Hibernate（对象关系映射、脏检查、JPQL）、Flyway 版本化迁移 |
| 数据库选型 | HSQLDB 内存库（本机实测）、MySQL / PostgreSQL / Redis（Redis 本机实测；MySQL/PG 概念讲解） |

这个阶段只涉及**单机数据库编程**（SQL/JDBC/连接池/事务/索引/Redis 缓存/MyBatis/JPA/Flyway），**不涉及 Web 层与框架的数据库集成**（Servlet/Spring MVC 中怎么管事务与数据源——[ph14 Web 后端开发阶段](../ph14-web-backend/14-web-backend.md) / [ph15 Spring 全家桶阶段](../ph15-spring-family/15-spring-family.md)，roadmap 第 15 节）、**不涉及分布式数据库、分库分表与分布式事务**（ph16 微服务与分布式阶段，roadmap 第 16 节，目录待建）、**不涉及消息队列中的持久化与搜索索引**（ph17 消息队列与搜索阶段，roadmap 第 17 节，目录待建）、**不涉及缓存一致性、缓存穿透/击穿/雪崩等高并发缓存架构**（ph18 缓存与高并发阶段，roadmap 第 18 节，目录待建）、**不涉及数据库运维与 CI/CD 中的迁移落地**（ph19 DevOps 与部署阶段，roadmap 第 19 节，目录待建）。本阶段承接 ph12——那里的 HSQLDB 集成测试证明了「代码 + SQL 能协作」，本阶段把「能协作」升级为「协作得对、快、稳」。

## 2. 来源与演变

**SQL** 诞生于 1970 年代 IBM 的 System R 项目（Edgar F. Codd 的关系模型论文 1970 年发表，1974 年 Donald Chamberlin 与 Raymond Boyce 设计出 SEQUEL 语言，即 SQL 前身），1979 年 Oracle 发布首个商业关系数据库。SQL 是声明式语言——**你描述「要什么」，数据库决定「怎么做」**，这个设计哲学让「查询优化」成为数据库引擎的核心能力，也让「索引改变执行计划」成为本阶段的关键心智。1986 年 SQL 成为 ANSI 标准，此后 1992 年 SQL-92、1999 年 SQL:1999（引入递归查询、窗口函数雏形）、2003 年 SQL:2003（窗口函数、XML）持续演进，各厂商（MySQL/PostgreSQL/Oracle）在标准之上叠加方言。

**JDBC**（Java Database Connectivity）1997 年随 JDK 1.1 发布，是 Java 访问数据库的**官方标准 SPI**：定义 `Driver` / `Connection` / `Statement` / `PreparedStatement` / `ResultSet` 五个核心接口，数据库厂商实现驱动接入。JDBC 的四个演进节点：JDBC 1.0 基本连接与查询 → JDBC 2.0（1998，随 JDK 1.2 发布：`ResultSet` 滚动/可更新、批量更新）→ JDBC 3.0（2002，随 J2SE 1.4 发布：`Savepoint`、`ConnectionEvent` 等）→ JDBC 4.0（2006，**自动驱动加载**——`DriverManager` 通过 `META-INF/services` 服务发现机制自动注册驱动，从此不再需要 `Class.forName`）。**连接池**的标准化晚于池化实践：连接池标准接口 `ConnectionPoolDataSource` / `PooledConnection` 随 **JDBC 2.0 Optional Package**（`javax.sql`，1999 年前后）才定义，更早的池化是各家自研（Apache DBCP 追溯至 2001 年后的 Jakarta Commons）；核心动机是「建连成本高」——TCP 握手 + 认证 + 会话初始化通常要几毫秒到几十毫秒，而一条 SQL 执行只要亚毫秒，池化把建连成本摊到启动期。

**Redis** 2009 年由 Salvatore Sanfilippo 发布，定位「内存中的数据结构服务器」——不是普通 KV 缓存，而是支持 String/Hash/List/Set/ZSet 五种数据结构、单线程事件循环驱动的内存数据库。它的价值在于**内存随机访问是微秒级**（比磁盘快 2~3 个数量级），配合 `EXPIRE/TTL` 过期机制成为缓存事实标准。**ORM** 的演化线：2002 年 Hibernate 发布（把 Java 对象映射到关系表，对象关系阻抗失配的经典解法）→ 2006 年 Sun 推出 **JPA 规范**（Java Persistence API，Hibernate 是其主要实现）→ **MyBatis** 2010 年从 Apache iBATIS 迁移而来（「半 ORM」：SQL 由开发者写，框架只做参数绑定与结果映射，2013 年迁至 GitHub 后成为国内 Java 生态主流）。**迁移工具** Flyway 2010 年由 Axel Fontaine 创建（版本化 SQL 迁移：DDL 进版本库、按版本号顺序执行、历史记录在 `flyway_schema_history` 表），2016 年并入 Boxfuse，Liquibase 2006 年出现（基于变更集 XML/YAML 描述，不写裸 SQL 也可迁移）。

| 版本/里程碑 | 年份 | 主要变化 |
|-----------|------|---------|
| SQL（System R / SEQUEL） | 1974 | Codd 关系模型落地为声明式查询语言，数据库负责优化执行 |
| SQL-92 | 1992 | 首个被广泛实现的标准基线，本阶段 SQL 语法基本属于 SQL-92 |
| JDBC 1.0 | 1997 | `Driver/Connection/Statement/ResultSet` 五个核心接口 |
| JDBC 2.0 | 1998 | 滚动/可更新 `ResultSet`、批量更新（`addBatch`，见 examples/ex04） |
| JDBC 3.0 | 2002 | `Savepoint`、`ConnectionEvent` 等（连接池标准接口属 JDBC 2.0 Optional Package） |
| JDBC 4.0 | 2006 | 服务发现自动加载驱动，`Class.forName` 成为历史 |
| Hibernate | 2002 | 首个主流 ORM，对象关系映射的开创者 |
| JPA 1.0 | 2006 | Sun 推出持久化规范，Hibernate 是参考实现（见 examples/ex07） |
| Redis | 2009 | 内存数据结构服务器，单线程事件循环 + 过期机制（见 examples/ex05） |
| MyBatis | 2010 | iBATIS 迁至 GitHub：SQL 开发者自写，框架做绑定与映射（见 examples/ex06） |
| Flyway | 2010 | 版本化 SQL 迁移，`flyway_schema_history` 记录已执行版本 |
| HikariCP | 2013 | 高性能连接池，「光」之意，Spring Boot 2 起为默认连接池（见 examples/ex03） |

本文示例以 **OpenJDK 17.0.18 + Maven 3.9.12 + HSQLDB 2.5.0** 为基线（验证工具链：`javac -version` → 17.0.18、`mvn -version` → 3.9.12；配套 **HikariCP 5.0.1、Jedis 3.9.0、MyBatis 3.5.19、Flyway 9.22.3、Hibernate 6.5.3.Final** 全部本机实测通过；**Redis 用本机 redis-server 实测**——examples/ex05 会临时拉起独立端口的真实 Redis 进程；**MySQL / PostgreSQL 未在本环境安装**，只做概念讲解与方言差异说明，可实测的替代路线是 HSQLDB 内存库）。本机 Maven 用 `mvn -o` 离线模式，依赖/插件取自本地仓库缓存（沙箱禁止写 `~/.m2`，用 `-Dmaven.repo.local=/tmp/m2clone` 指向可写目录的克隆；正常联网环境直接 `mvn test` 即可）。SQL 与 JDBC 的 API 自 JDBC 4.0 定型以来高度稳定，二十年前写的 `PreparedStatement` 代码今天依然能编译运行——这是 Java 生态「向后兼容」传统在数据访问层的体现。

## 3. 语法与参数

### 3.1 JDBC 连接与 CRUD：从 DriverManager 到 PreparedStatement

JDBC 编程的最小闭环：**拿连接 → 建语句 → 绑参数 → 执行 → 读结果 → 关资源**。连接用 `DriverManager.getConnection(jdbcUrl, user, password)`（JDBC 4.0 起驱动自动注册，无需 `Class.forName`），语句分三类：

| 语句类型 | 用途 | 参数 | 说明 |
|---------|------|------|------|
| `Statement` | DDL、无参数语句 | 拼接 SQL | 没有用户输入时可用；有输入就有注入风险 |
| `PreparedStatement` | 带参数的 DML/查询 | `?` 占位符 + `setXxx` | **预编译 + 参数转义**，防注入的根基 |
| `CallableStatement` | 存储过程调用 | `?` 占位符 | 本阶段不展开（数据库进阶内容） |

```java
// examples/ex01-jdbc-basics/src/main/java/com/example/UserDao.java —— 参数化 CRUD（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + HSQLDB 2.5.0 + JUnit Jupiter 5.10.1，测试命令：cd examples/ex01-jdbc-basics && mvn test（已验证）
public long insert(String name, String email) throws SQLException {
    try (PreparedStatement ps = conn.prepareStatement(
            "INSERT INTO users(name, email) VALUES (?, ?)",
            Statement.RETURN_GENERATED_KEYS)) {   // 声明要取回数据库生成的主键
        ps.setString(1, name);   // 占位符从 1 开始编号
        ps.setString(2, email);
        ps.executeUpdate();
        try (ResultSet keys = ps.getGeneratedKeys()) {
            keys.next();
            return keys.getLong(1);   // 自增主键由数据库生成，回填给调用方
        }
    }   // try-with-resources：PreparedStatement 自动关闭，无需 finally
}
```

**PreparedStatement 为什么防注入**：`?` 占位符把「SQL 结构」与「参数数据」分离——参数经驱动**转义后作为纯数据传输**，永远不会被拼进 SQL 文本，所以 `x'); DROP TABLE users;--` 这样的注入载荷只会被原样存进表里。examples/ex01 的 `parameterization_treatsInjectionPayloadAsPlainData` 测试实测验证：插入注入载荷后表安然无恙，数据被当作普通字符串保存。**对比**：用 `Statement` 拼字符串是注入温床，**凡是带用户输入的 SQL 一律走 `PreparedStatement`**——这是本阶段最重要的安全习惯。

**ResultSet 游标语义**：`ResultSet` 初始位置在第一行**之前**，必须先 `next()` 移动游标再取值；`next()` 返回 `false` 表示没有下一行（查询无结果）。`findById` 返回 `Optional<User>` 的映射模式（`rs.next() ? Optional.of(...) : Optional.empty()`）是 JDBC 层的惯用法。

**executeUpdate 返回值**：DML 语句返回**受影响行数**——`UPDATE`/`DELETE` 返回 0 行意味着「目标不存在」，可以据此判断操作是否命中，不用先 `SELECT` 再判断（examples/ex01 的 `updateEmail(999L, ...)` 断言返回 0）。

**表结构约束**：`CREATE TABLE` 里 `NOT NULL`、`UNIQUE`、`CHECK` 是**数据库层的数据完整性**，与 Java 层的业务校验各司其职——Java 校验「输入合理」（快速失败、报错信息友好），数据库约束兜底「数据合法」（并发下也无法绕过），examples/ex01 实测：重复邮箱插入被 `UNIQUE` 约束拒绝并抛 `SQLException`。

### 3.2 事务：原子性、边界与回滚语义

事务的四个特性 **ACID**：**原子性**（Atomicity，一组操作同生同死）、**一致性**（Consistency，事务前后数据都满足约束）、**隔离性**（Isolation，并发事务互不干扰）、**持久性**（Durability，提交后数据不丢）。JDBC 层控制事务的三个 API：

| API | 作用 |
|-----|------|
| `conn.setAutoCommit(false)` | 关闭自动提交——**事务从这里开始**，后续语句属于同一个事务 |
| `conn.commit()` | 提交——事务的写入落盘，对其它连接可见 |
| `conn.rollback()` | 回滚——撤销本事务的全部写入，数据库回到事务前状态 |

```java
// examples/ex02-transaction-transfer/src/main/java/com/example/AccountDao.java —— 转账事务（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + HSQLDB 2.5.0，测试命令：cd examples/ex02-transaction-transfer && mvn test（已验证）
public void transferCents(long fromId, long toId, long amountCents) throws SQLException {
    boolean prevAutoCommit = conn.getAutoCommit();
    conn.setAutoCommit(false);   // —— 事务从这里开始
    try {
        // 1. 扣款：WHERE 里带余额条件，余额不足时影响 0 行
        try (PreparedStatement debit = conn.prepareStatement(
                "UPDATE accounts SET balance_cents = balance_cents - ? WHERE id = ? AND balance_cents >= ?")) {
            // ... 影响 0 行则抛业务异常
        }
        // 2. 收款：账户不存在时影响 0 行——此刻扣款已发生，必须回滚
        try (PreparedStatement credit = conn.prepareStatement(
                "UPDATE accounts SET balance_cents = balance_cents + ? WHERE id = ?")) {
            // ...
        }
        conn.commit();   // —— 两步都成功，事务落盘
    } catch (SQLException | RuntimeException e) {
        conn.rollback();   // —— 任何一步失败，撤销本事务的全部写入
        throw e;
    } finally {
        conn.setAutoCommit(prevAutoCommit);   // 恢复现场，连接可复用
    }
}
```

**事务边界必须由业务定义**：数据库不知道「一次转账」的边界在哪，是 `setAutoCommit(false)` 到 `commit()` 之间的代码段定义了这个边界——扣款 + 收款这两步「同生同死」，缺一不可。**回滚语义实测**（examples/ex02 的 `missingPayee_rollsBackTheDebit`）：第 1 步扣款执行成功、第 2 步收款失败（收款账户不存在）→ `rollback` 撤销第 1 步的扣款，断言余额分毫不变——「扣款语句实际执行过，没有回滚机制的话这里只剩 70」，这是 rollback 语义的直接证据。

**事务的两个关键写法**：

- **恢复现场**：`finally` 里把 autoCommit 恢复为调用前的值——连接池里的连接会被复用，不恢复会把「事务状态」泄漏给下一位借用者
- **抛出的异常类型**：`SQLException | RuntimeException` 都捕获回滚——业务失败（余额不足）与数据库故障（连接中断）都必须撤销已做的写入

> 本阶段只讲**单连接上的本地事务**（`commit`/`rollback`）。**跨库/跨服务的分布式事务**（2PC、TCC、Saga）属于 ph16 微服务与分布式阶段，这里只需理解「事务边界由业务定义」这一条心智。

### 3.3 连接池：HikariCP 的借还与复用

**连接是昂贵的资源**：一次数据库连接 = TCP 握手 + 认证 + 会话初始化（协议协商、字符集、事务默认设置），耗时毫秒级，而一条 SQL 执行常只要亚毫秒——**每请求建连是灾难**。连接池的核心心智：**预先建好 N 条常驻物理连接，业务「借了还、还了再借」，把建连成本摊到启动期**。HikariCP 是当前事实标准（Spring Boot 2+ 默认连接池），配置核心参数：

| 参数 | 含义 | 本阶段建议 |
|------|------|-----------|
| `maximumPoolSize` | 池中物理连接上限 | 按并发峰值定，并非越大越好（连接占内存与数据库资源） |
| `minimumIdle` | 池保持的最小空闲连接 | 默认与 maximumPoolSize 相同（HikariCP 偏好全量常驻） |
| `connectionTimeout` | 借连接最长等待时间 | 默认 30s；池满时请求排队等待 |
| `maxLifetime` | 连接最长存活时间 | 略小于数据库的 wait_timeout |

```java
// examples/ex03-hikari-pool/src/main/java/com/example/TaskDao.java —— HikariCP 池化（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + HikariCP 5.0.1 + HSQLDB 2.5.0，测试命令：cd examples/ex03-hikari-pool && mvn test（已验证）
public long insert(String title) throws SQLException {
    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO tasks(title) VALUES (?)", Statement.RETURN_GENERATED_KEYS)) {
        ps.setString(1, title);
        ps.executeUpdate();
        try (ResultSet keys = ps.getGeneratedKeys()) {
            keys.next();
            return keys.getLong(1);
        }
    }
}
```
**「关闭」其实是「归还」**：从池里借出的 `Connection`，`close()` 语义被池包装成「放回池里」，物理连接不关闭——调用方无感知，但必须**用完就关**（try-with-resources），否则连接被占用、池被借空。examples/ex03 实测了两个关键行为：

- **连接复用**：串行借还 200 次，池的物理连接总数始终 ≤ 4（`poolStats()` 读 `HikariPoolMXBean` 的 total/active/idle）——200 次操作全靠复用 4 条连接
- **并发排队**：8 线程并发写 200 次、池上限 4，也能全部成功——池满时借连接会排队等待（`connectionTimeout` 内），小池扛大流量靠的是排队而非无限建连

### 3.4 索引与慢查询：执行计划与代价权衡

**没有索引的等值查询 = 全表扫描**：数据库逐行比对，成本随行数**线性增长**（O(N)）；**有索引 = 走 B+ 树定位**：从根节点沿路径二分查找，成本约 **O(log N)**。但索引不是免费的——**写入时要同步维护索引**，所以「索引影响查询和写入成本」：读多写少的列值得建索引，写密集的表不能乱建。查看数据库怎么执行一条查询，用**执行计划**（HSQLDB 是 `EXPLAIN PLAN FOR <sql>`，MySQL 是 `EXPLAIN`，PostgreSQL 是 `EXPLAIN ANALYZE`）：

```java
// examples/ex04-index-slowquery/src/main/java/com/example/IndexLab.java —— 执行计划（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + HSQLDB 2.5.0，测试命令：cd examples/ex04-index-slowquery && mvn test（已验证）
public String planFor(String sql) throws SQLException {
    StringBuilder plan = new StringBuilder();
    try (PreparedStatement ps = conn.prepareStatement("EXPLAIN PLAN FOR " + sql);
         ResultSet rs = ps.executeQuery()) {
        while (rs.next()) {
            plan.append(rs.getString(1)).append('\n');
        }
    }
    return plan.toString();
}
```

examples/ex04 在 HSQLDB 里造了 **20000 行**数据，实测三个对照：

| 对照 | 实测结果 |
|------|---------|
| 建索引前 `EXPLAIN PLAN FOR` | 计划含 `access=FULL SCAN`（全表扫描） |
| 建索引后 `EXPLAIN PLAN FOR` | 计划出现 `IDX_USERS_EMAIL`（走索引），不再全表扫描 |
| 同一等值查询 ×100 计时 | **无索引 78 ms → 有索引 1 ms**（本机实测，20000 行） |

**批量造数技巧**：`addBatch` + `executeBatch` 把 N 条 INSERT 攒成一次网络往返提交，关自动提交后 `commit()` 一次落盘——examples/ex04 的 `seed(20000)` 就是这么造的数（比逐条 executeUpdate 快一个数量级）。

### 3.5 Redis 与 RESP 协议：缓存与高频状态

Redis 是**内存中的 KV 数据库**，通过 TCP 端口（默认 6379）与客户端通信，协议叫 **RESP**（REdis Serialization Protocol）。理解 RESP 是理解「客户端库到底做了什么」的关键——**Jedis/Lettuce 的底层就是手写 RESP 帧**：

| RESP 类型 | 首字节 | 示例 |
|-----------|--------|------|
| 简单字符串 | `+` | `+OK` |
| 错误 | `-` | `-ERR unknown command` |
| 整数 | `:` | `:1` |
| 批量字符串 | `$` | `$5\r\nhello`（`$-1` 表示 nil/不存在） |
| 数组 | `*` | `*2\r\n$3\r\nfoo\r\n$3\r\nbar` |

```java
// examples/ex05-redis/src/main/java/com/example/RespClient.java —— 手写 RESP 客户端（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + 本机 redis-server，测试命令：cd examples/ex05-redis && mvn test（已验证）
public Object command(String... args) throws IOException {
    StringBuilder sb = new StringBuilder();
    sb.append('*').append(args.length).append("\r\n");
    for (String arg : args) {
        byte[] bytes = arg.getBytes(StandardCharsets.UTF_8);
        sb.append('$').append(bytes.length).append("\r\n");
        out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        sb.setLength(0);
        out.write(bytes);
        out.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }
    out.flush();
    return readReply();   // 按首字节解析响应（+/-/:/$/*）
}
```

examples/ex05 是本阶段唯一需要**外部服务**的示例：测试用 `RedisServerHandle` 临时拉起一个独立端口（6399）的真实 `redis-server` 进程，`@BeforeAll` 启动、`@AfterAll` 关闭——**不测 mock 出来的 Redis，测真实服务**。实测内容：

- 手写 `RespClient` 对真实 Redis 做 `PING`/`SET`/`GET`/`DEL`/`EXPIRE`/`TTL` 全往返；`TTL` 语义实测：存在的键返回剩余秒数、不存在的键返回 **-2**、无过期返回 **-1**
- `Jedis` 客户端做同一件事——对照「手写协议 vs 客户端库」：库封装的就是 RESP 帧
- **Cache-Aside 缓存旁路**（缓存策略的基本型）：先查缓存，未命中回源（数据库）并回填缓存（带过期时间兜底）；第二次缓存命中时不再回源——实测中「删掉数据库」后仍能读到值，证明读的是缓存

> 本阶段只讲**缓存旁路（Cache-Aside）这一种基本策略**。**缓存一致性、缓存穿透/击穿/雪崩、分布式锁的 Redis 实现**属于 ph18 缓存与高并发阶段，这里只需理解「缓存是数据库前面的加速层，过期时间防脏数据永生」。

### 3.6 MyBatis 与 Flyway：SQL 映射与版本化迁移

**MyBatis 是「半 ORM」**：SQL 由开发者**亲手写**（在 XML 或注解里），框架只做两件事——把 Java 参数绑定进 SQL（`#{}` 占位符，底层仍是 PreparedStatement）、把查询结果映射成 Java 对象。适合 SQL 复杂、需要精细控制查询语句的场景：

```java
// examples/ex06-mybatis-flyway/src/main/java/com/example/UserMapper.java —— Mapper 接口（完整版见 examples/）
// 方法签名即数据访问契约，SQL 在同名 XML（UserMapper.xml）里
public interface UserMapper {

    long insert(User user);

    User findById(long id);

    List<User> findAll();

    int updateEmail(@Param("id") long id, @Param("email") String email);

    int delete(long id);
}
```

```xml
<!-- examples/ex06-mybatis-flyway/src/main/resources/com/example/UserMapper.xml —— SQL 映射（完整版见 examples/） -->
<!-- id 绑定方法名；#{} 是安全的参数占位（底层仍是 PreparedStatement） -->
<mapper namespace="com.example.UserMapper">
  <insert id="insert" useGeneratedKeys="true" keyProperty="id">
    INSERT INTO users(name, email) VALUES (#{name}, #{email})
  </insert>
  <select id="findById" resultType="com.example.User">
    SELECT id, name, email FROM users WHERE id = #{id}
  </select>
</mapper>
```

**Flyway 是数据库的版本控制**：DDL 进版本库，按 `V1__描述.sql`、`V2__描述.sql` 的**版本号顺序**执行，已执行的版本记录在 `flyway_schema_history` 表（幂等——重复运行自动跳过已执行版本）。schema 演进 = 新增一个迁移文件，**永不修改已执行的旧文件**（改旧文件 = 篡改历史，Flyway 会报校验失败）。examples/ex06 实测：`V1` 建 users 表、`V2` 给 email 加索引，迁移后 `flyway_schema_history` 正确记录两个版本；MyBatis 在 Flyway 迁移出的表上做完整 CRUD（`useGeneratedKeys` 回填自增主键、`update/delete` 返回受影响行数）。

**MyBatis 的事务**：`mybatis-config.xml` 里 `transactionManager type="JDBC"` 表示事务边界由 `SqlSession.commit()` / `rollback()` 控制——写操作必须显式 `session.commit()`，否则不落盘（examples/ex06 的测试里每个写操作后都显式提交）。

### 3.7 JPA / Hibernate：对象关系映射与脏检查

**JPA（Jakarta Persistence API）是规范，Hibernate 是它的实现**。与 MyBatis「SQL 自写」相反，JPA 的哲学是**你操作对象，Hibernate 生成 SQL**——`@Entity` 注解把类映射到表、属性映射到列，`persist()` 生成 INSERT、`find()` 生成 SELECT：

```java
// examples/ex07-jpa-hibernate/src/main/java/com/example/Book.java —— JPA 实体（完整版见 examples/）
// 验证环境：OpenJDK 17.0.18 + Hibernate 6.5.3.Final + HSQLDB 2.5.0，测试命令：cd examples/ex07-jpa-hibernate && mvn test（已验证）
@Entity
@Table(name = "books")
public class Book {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 128)
    private String title;

    /** JPA 要求实体有 protected/public 无参构造（代理与反射用） */
    protected Book() {}
}
```

**JPA 的三个核心心智**（examples/ex07 实测脏检查与 JPQL，一级缓存为语义说明）：

- **脏检查（dirty checking）**：实体被 `persist` 后进入「托管状态」，此时**改了字段、commit 时 Hibernate 自动生成 UPDATE**——没有调用任何 update 方法，Hibernate 比对快照只把变化的列发 UPDATE
- **持久化上下文与一级缓存**：`Session` 是持久化上下文，同一 `Session` 内 `find` 同一主键只查一次库（快照比对的前提）
- **JPQL 面向对象**：`from Book where title like :kw` 写的是**类名与属性**（`Book` 不是 `books`），Hibernate 翻译成 SQL——「面向对象而不是面向表」

**ORM 不是银弹**：SQL 简单时 JPA 省代码，SQL 复杂（多表 join、窗口函数、分库分表）时 MyBatis 的显式 SQL 更可控——**「SQL 基础比 ORM 更重要」**的含义是：不懂 SQL 的人用 ORM 只会写出慢查询与 N+1 问题。ORM 是「生成 SQL 的工具」，不是「不用学 SQL 的借口」。

### 3.8 高频坑一览

| 坑 | 现象 | 正确姿势 |
|----|------|---------|
| 用 `Statement` 拼 SQL | SQL 注入 | 一切带用户输入的 SQL 走 `PreparedStatement` |
| `ResultSet` 不先 `next()` 就取值 | `SQLException: no data` / 取到首行前的空值 | 记住游标初始在第一行之前 |
| 忘了 `finally` 关连接 | 连接池被借空、连接泄漏 | try-with-resources，用完即「归还」 |
| 事务失败不回滚 | 半拉子写入（只扣款没收款） | `catch` 里 `rollback`，`finally` 里恢复 autoCommit |
| 池连接状态泄漏 | 上一位借者的事务状态带过来 | `finally` 恢复 autoCommit（见 3.2） |
| 见列就建索引 | 写入变慢、索引膨胀 | 只为「查询高频 + 选择性高」的列建索引 |
| 忘了 `session.commit()` | MyBatis 写操作不落盘 | JDBC 事务管理器下显式提交 |
| 缓存不过期 | 脏数据永生 | `SETEX`/`EXPIRE` 设置 TTL 兜底 |
| 改已执行的 Flyway 迁移文件 | Flyway 校验失败 | schema 演进 = 新增 V<N+1> 文件，永不改旧文件 |
| 不懂 SQL 就上 ORM | N+1 查询、慢查询 | SQL 基础比 ORM 更重要（本阶段必会概念 1） |

## 4. 底层原理

### 4.1 JDBC 驱动架构：DriverManager 与服务发现

JDBC 四层架构：**应用代码 → JDBC API（接口）→ 厂商驱动（实现）→ 数据库引擎**。JDBC 4.0 的自动驱动加载靠 `META-INF/services/java.sql.Driver` 服务发现机制：`DriverManager.getConnection()` 时，ClassLoader 扫描 classpath 里所有 jar 的 `META-INF/services` 文件，实例化声明的驱动类，逐个询问「你能连这个 URL 吗」（`acceptsURL`），能连的驱动建立连接。

```text
JDBC 应用（UserDao / AccountDao）
      │ 调用 java.sql.* 接口
      ▼
java.sql.Connection / PreparedStatement / ResultSet   ← JDBC 标准接口
      │
      ▼
HSQLDB 驱动（org.hsqldb.jdbc.JDBCDriver）   ← 厂商实现
      │ 协议（内存共享 / TCP）
      ▼
数据库引擎（HSQLDB 内存库 / MySQL / PostgreSQL …）
```

- **`Connection` 是「会话」不是「连接」**：一条物理 TCP 连接上可以有多个逻辑会话状态（autoCommit、隔离级别、字符集），所以 `setAutoCommit(false)` 是**会话级**状态——这正是不恢复现场会污染连接池的根因
- **`PreparedStatement` 的「预编译」**：参数化后，SQL 文本（含占位符）可被数据库**预解析/预优化**一次、重复执行只换参数——MySQL 默认客户端模拟预编译（每次仍会解析），但**参数转义**在任何驱动里都生效，这是防注入的根本保证

### 4.2 事务的落盘机制：undo 日志与回滚

数据库保证原子性的经典机制是 **undo 日志（回滚日志）**：事务每修改一行，先往 undo 日志写「修改前的旧值」。`commit` 时只需把 undo 日志标记为「已提交」并让修改对其它事务可见；`rollback` 时按 undo 日志倒序把旧值**反向应用**回去——**回滚不是「撤销操作」，而是「用旧值覆盖回去」**，所以即使扣款语句已经执行（内存缓冲/磁盘页已改），rollback 依然能把余额恢复到事务前。

```text
事务开始 ──▶ UPDATE 扣款 ──▶ 写 undo 日志（旧余额 100）──▶ 改数据页为 70
                      ──▶ UPDATE 收款失败 ──▶ 抛异常
rollback ──▶ 按 undo 日志反向应用：余额 70 ──▶ 恢复为 100
commit   ──▶ undo 日志标记已提交 ──▶ 修改对外可见、持久化
```

- **崩溃恢复**：数据库崩溃重启后，redo 日志保证「已提交的不丢」（持久性），undo 日志保证「未提交的撤销」（原子性）——ACID 的 D 与 A 各自由两类日志兑现
- **隔离性与锁**：`UPDATE` 会加行锁，未提交事务的修改对其它事务不可见（读已提交/可重复读）——本阶段用单连接测回滚语义，**并发隔离级别的差异**（脏读/幻读/可重复读）属于 ph16 微服务与分布式阶段的并发数据库内容，这里了解「回滚靠 undo 日志」即可

### 4.3 连接池的复用机制：借出、归还与健康检查

连接池的实现是经典的**资源池模式**：启动时按 `minimumIdle` 预热建连，维护一个「空闲连接队列」；借出时从队列取一条（队列空则新建到 `maximumPoolSize` 上限，再满则等待 `connectionTimeout`）；归还时把连接放回队列。HikariCP 的额外机制：

- **FastList 与并发优化**：借还操作避开 `Collections.synchronizedList` 的整表锁，用 lock-free 的专用集合（FastList）+ 细粒度锁，把借还延迟压到微秒级
- **连接保活（isValid / 探测）**：归还时或定期对连接做轻量探测（如 `SELECT 1`），踢掉失效连接；`maxLifetime` 到期后优雅退役——数据库 `wait_timeout` 会静默断掉闲置连接，池必须能发现并重建
- **泄漏防护**：连接借出超过阈值未归还，HikariCP 可记录泄漏堆栈——这就是「必须用完即关」的池侧保障

```text
业务线程 ──借──▶ 空闲队列（FastList）──空──▶ 新建（< maximumPoolSize）──满──▶ 等 connectionTimeout
业务线程 ──还──▶ 空闲队列 ──▶ 健康检查 ──失效──▶ 丢弃重建
连接龄 > maxLifetime ──▶ 优雅退役，池内补建新连接
```

### 4.4 B+ 树索引：为什么 O(log N) 能赢 O(N)

关系数据库主流索引结构是 **B+ 树**：所有数据都在**叶子节点**（有序链表），非叶子节点只存「键 + 指针」用于路由。查询时从根节点沿路径二分定位，树高通常 3~4 层——**一次查询只要 3~4 次磁盘 IO**（层高即 IO 次数），而全表扫描要读全部数据页。examples/ex04 实测的 78 ms → 1 ms 就是「3~4 次定位」对「扫 20000 行」的碾压。

```text
全表扫描（无索引）：逐行比对 email 列 ──▶ 读全部数据页 ──▶ O(N)
B+ 树索引（有索引）：根 ──▶ 中间层 ──▶ 叶子（有序）──▶ O(log N) ≈ 3~4 次 IO
写入时：INSERT/UPDATE/DELETE 同步维护索引树 ──▶ 写成本增加
```

- **索引为什么不是越多越好**：每次写入都要同步维护所有索引树（写放大），索引占磁盘，优化器还要在多个索引里选——所以「索引影响查询和写入成本」，建索引前先想清楚这条查询高频吗、这个列选择性高吗
- **覆盖索引**：`SELECT email FROM users WHERE email = ?` 若索引含全部所需列，可只扫索引不碰数据页（Index-Only Scan）——本阶段了解概念即可，实践在 ph18 高并发阶段
- **执行计划是数据库的「选择」**：`EXPLAIN` 显示的是优化器基于统计信息（行数、分布）选定的执行方式，索引建了但选择性太差时优化器仍会全表扫描——**用执行计划验证，而不是假设**

### 4.5 Redis 单线程事件循环与过期机制

Redis 是**单线程事件循环**（epoll/kqueue 多路复用）驱动的：所有命令在一个线程里串行执行，天然无锁、无并发竞争——这是它「快」与「简单」的来源，代价是**单条命令必须快速完成**（O(N) 命令如 `KEYS *` 会阻塞整个服务）。持久化（RDB 快照 / AOF 追加）由**子进程/后台线程**完成，不阻塞主事件循环。

**过期机制是「懒过期 + 主动过期」**（examples/ex05 实测的 TTL 语义）：

- **懒过期**：访问键时才检查是否过期，过期即删（`GET` 返回 nil）
- **主动过期**：后台定时抽样检查，把过期键批量删除，防止「永不被访问的过期键」占内存
- 所以 `TTL` 返回值：键存在且有 TTL → 剩余秒数；键存在无 TTL → **-1**；键不存在 → **-2**（实测断言）

```text
客户端 ──SET/GET/DEL──▶ TCP ──▶ 单线程事件循环 ──▶ 内存哈希表（微秒级）
                                   │
                                   ├─ 懒过期：访问时检查
                                   ├─ 主动过期：定时抽样删除
                                   └─ 持久化：RDB/AOF 由子进程做（不阻塞）
```

### 4.6 ORM 的反射与代理：MyBatis 与 Hibernate 分别做了什么

- **MyBatis**：启动时解析 `mybatis-config.xml` 与各 `*Mapper.xml`，把 `namespace + id` 注册成语句；`session.getMapper(UserMapper.class)` 用 **JDK 动态代理**生成接口实现——调用 `findById(1)` 时，代理按方法名查已解析的 SQL，用 `#{}` 参数做 `PreparedStatement` 绑定，执行后按 `resultType` 反射创建对象、按列名 set 属性。**开发者看到的「接口方法」其实是一个代理方法**，SQL 的解析与执行全在代理里。
- **Hibernate**：`Session` 维护**持久化上下文**（一级缓存 + 实体快照）。`persist` 后实体进上下文，`find` 先查上下文缓存（命中不查库）；`commit` 时对上下文里每个托管实体**比对快照**——字段变了才生成 `UPDATE`（脏检查），没变不发任何 SQL。实体的「托管/游离/瞬态」三态由上下文管理，`close()` 后实体游离、快照失效。

| 对比维度 | MyBatis | JPA / Hibernate |
|---------|---------|-----------------|
| SQL 由谁写 | 开发者（XML/注解） | Hibernate 生成（JPQL 翻译） |
| 核心机制 | JDK 动态代理 + XML 解析 | 持久化上下文 + 脏检查快照 |
| 适合 | SQL 复杂、需精细控制 | CRUD 为主、模型简单 |
| 风险 | 手动 SQL 易漏参数 | N+1 查询、生成的 SQL 不可控 |
| 本阶段落点 | examples/ex06 | examples/ex07 |

## 5. 使用场景

| 场景 | 涉及知识点 | 落点 |
|------|-----------|------|
| 任何需要持久化的业务数据（用户、订单、设备状态） | JDBC 参数化 CRUD + 表约束兜底完整性 | examples/ex01、exercises 练习 1、project/ |
| 资金/库存等「多步必须同生同死」的操作 | 事务：边界由业务定义，失败整体回滚 | examples/ex02、exercises 练习 2、project/ 批量导入 |
| 高并发访问数据库的服务 | 连接池：建连成本摊到启动期，借还复用 | examples/ex03、exercises 练习 3、project/ |
| 查询越来越慢的表 | 索引 + `EXPLAIN` 看执行计划，验证而非假设 | examples/ex04、exercises 练习 5 |
| 高频读、低频变的热数据（用户资料、配置） | Redis Cache-Aside + TTL 兜底 | examples/ex05、exercises 练习 4 |
| 需要精细控制 SQL 的团队/项目 | MyBatis：SQL 自写、绑定与映射交给框架 | examples/ex06 |
| 模型简单、CRUD 为主的业务 | JPA/Hibernate：对象操作，SQL 自动生成 | examples/ex07 |
| 数据库 schema 演进（加表/加索引/改列） | Flyway 版本化迁移：DDL 进版本库，幂等可复现 | examples/ex06、project/ |
| 与其它语言同类机制的对比（为 analysis/ 积累） | 见下方跨语言对比段落 | 全章 |

**不适合**此阶段的事项：

- **Web 层与框架的数据库集成**（Spring 的 `DataSource`/事务管理/`@Transactional`）——[ph14 Web 后端开发阶段](../ph14-web-backend/14-web-backend.md) / [ph15 Spring 全家桶阶段](../ph15-spring-family/15-spring-family.md)（roadmap 第 15 节）；本阶段用纯 JDBC/MyBatis/JPA 的裸 API
- **分库分表、读写分离与分布式事务**——ph16 微服务与分布式阶段（roadmap 第 16 节，目录待建）
- **消息队列的持久化与搜索索引**（Kafka/Elasticsearch 的数据存储机制）——ph17 消息队列与搜索阶段（roadmap 第 17 节，目录待建）
- **缓存穿透/击穿/雪崩、缓存一致性协议**——ph18 缓存与高并发阶段（roadmap 第 18 节，目录待建）
- **数据库运维**（备份恢复、主从复制、监控告警、迁移进 CI/CD）——ph19 DevOps 与部署阶段（roadmap 第 19 节，目录待建）

**跨语言对比（简短）**：Java 的 JDBC 是「接口标准 + 厂商驱动」，C++ 的常见路线是 libpq / mysql++（厂商 SDK 或薄封装），Go 的 `database/sql` 与 JDBC 同构（`sql.DB` 自带连接池，`db.QueryRow` 对应 `PreparedStatement` 心智），Python 的 DB-API 2.0 也走「连接 + 游标 + 参数化」同一模式——**数据访问的接口形状全语言收敛**，差异在连接池是否内置（Go 内置、Java 靠 HikariCP）。Redis 客户端在 Java（Jedis/Lettuce）、Python（redis-py）、Go（go-redis）里都是 RESP 协议的封装，协议本身与语言无关——这是为 analysis/ 与 Tenet 合成积累的素材。

## 6. 代码示例

> 本阶段示例全部**本机实测通过**（OpenJDK 17.0.18 + Maven 3.9.12；本环境沙箱禁止写默认本地仓库 `~/.m2`，Maven 用 `mvn -o` 离线模式、依赖/插件取自本地仓库缓存——正常联网环境直接 `mvn test` 即可）。ex01~ex07 均为可运行 Maven 工程；**ex05 需要本机 redis-server**（测试会临时拉起独立端口 6399 的真实 Redis 进程，无 redis-server 时测试报「请确认已安装 redis-server」）。

### 示例 1：JDBC 参数化 CRUD 与防注入（`examples/ex01-jdbc-basics/`）

`UserDao` 全量 CRUD：`RETURN_GENERATED_KEYS` 回填自增主键、`findById` 返回 `Optional<User>`、`UPDATE/DELETE` 返回受影响行数、UNIQUE 约束拒绝重复邮箱、**注入载荷被当纯数据存取**（`x'); DROP TABLE users;--` 安然入表），对应 3.1。实测：`mvn test` → `Tests run: 4`。

```bash
cd examples/ex01-jdbc-basics && mvn test   # 实测: Tests run: 4, Failures: 0
```

### 示例 2：事务转账与回滚语义（`examples/ex02-transaction-transfer/`）

`AccountDao.transferCents`：扣款 + 收款两步同生同死，`WHERE` 带余额条件守底线，任何一步失败整体回滚（**实测 `missingPayee_rollsBackTheDebit`：扣款执行过、回滚后余额分毫不变**），对应 3.2。实测：`Tests run: 3`（成功提交 / 余额不足回滚 / 收款方不存在回滚）。

### 示例 3：HikariCP 连接池（`examples/ex03-hikari-pool/`）

池化 CRUD + **连接复用实测**（串行 200 次借还、物理连接数 ≤ 4）+ **并发排队实测**（8 线程 × 25 次、池上限 4 全成功），`poolStats()` 读池实时状态，对应 3.3。实测：`Tests run: 3`。pom 中「离线版本仲裁」注释的 slf4j-api 依赖为沙箱离线所需，正常联网环境可删除。

### 示例 4：索引与执行计划（`examples/ex04-index-slowquery/`）

20000 行造数 + `EXPLAIN PLAN FOR` 对照（无索引 `FULL SCAN` → 有索引 `IDX_USERS_EMAIL`）+ **计时对比实测：无索引 78 ms → 有索引 1 ms（×100 次等值查询）**，对应 3.4。实测：`Tests run: 3`。

```bash
cd examples/ex04-index-slowquery && mvn test   # 实测输出: [IndexLab] 20000 行 × 100 次等值查询: 无索引 78 ms, 有索引 1 ms
```

### 示例 5：Redis：手写 RESP 客户端 + Jedis + Cache-Aside（`examples/ex05-redis/`）

`RespClient` 零依赖手写 RESP2 协议（`*N\r\n` 数组 + `$len\r\n` 批量字符串），对**真实 redis-server** 做 `SET/GET/DEL/EXPIRE/TTL` 全往返；`JedisClientTest` 用官方客户端做同一件事并演示 **Cache-Aside 缓存旁路**（第二次命中不再回源），对应 3.5。实测：`Tests run: 4`（RespClientTest 2 + JedisClientTest 2）。**前置条件：本机安装 redis-server**（测试用 `RedisServerHandle` 临时拉起端口 6399，`--save ""` 不落盘）。

### 示例 6：MyBatis + Flyway 联调（`examples/ex06-mybatis-flyway/`）

Flyway 先迁移（`V1` 建 users 表、`V2` 加 email 索引），MyBatis 接管数据访问：`useGeneratedKeys` 回填主键、`#{}` 安全占位、JDBC 事务管理器下显式 `session.commit()`，对应 3.6。实测：`Tests run: 3`（迁移历史 / insert+find / update+delete）。

### 示例 7：JPA / Hibernate 实体与脏检查（`examples/ex07-jpa-hibernate/`）

`Book` 实体注解映射 + `persist/find` 自增主键回填 + **脏检查实测**（托管对象改字段、commit 自动发 UPDATE）+ JPQL 面向对象查询，对应 3.7。实测：`Tests run: 3`。pom 中「离线版本仲裁」注释的三项依赖（jakarta.xml.bind-api / jboss-logging / byte-buddy）为沙箱离线所需，正常联网环境可删除。

## 7. 总结

### 关键要点

1. **SQL 基础比 ORM 更重要**：`PreparedStatement` 参数化防注入、`ResultSet` 游标先 `next()`、`executeUpdate` 返回受影响行数——这些 JDBC 基本功是 ORM 之上的地基；不懂 SQL 的人用 ORM 只会写慢查询与 N+1
2. **事务边界必须由业务定义**：`setAutoCommit(false)` 到 `commit()` 之间的代码段就是边界；任何一步失败 `rollback` 撤销全部写入（实测：扣款执行过、回滚后余额分毫不变）；`finally` 恢复 autoCommit 防池污染
3. **连接必须池化**：建连毫秒级、SQL 亚毫秒，每请求建连是灾难；HikariCP 借还复用，`close()` 是归还不是断开，用完即关防泄漏
4. **索引影响查询和写入成本**：全表扫描 O(N) vs B+ 树 O(log N)（实测 78 ms → 1 ms）；写入要同步维护索引树；用 `EXPLAIN` 验证执行计划而非假设
5. **Redis 适合缓存和高频状态**：RESP 协议是客户端库的底层；Cache-Aside 先查缓存、未命中回源回填、TTL 防脏数据永生；单线程事件循环是它快与简单的原因
6. **ORM 三分天下按场景选**：MyBatis SQL 自写（复杂 SQL 可控）、JPA/Hibernate 对象操作（CRUD 高效，脏检查自动 UPDATE）、Flyway 管 schema 版本（DDL 进版本库、幂等、永不改旧迁移）
7. **数据完整性分层**：Java 层业务校验快速失败 + 数据库约束（NOT NULL/UNIQUE/CHECK）并发兜底——两层各有分工，实测重复邮箱被 UNIQUE 拒绝
8. **集成测试要测真实引擎**：HSQLDB 内存库（纯 Java 秒级）+ Redis 真实进程（测试拉起独立端口）——「代码 + SQL + 引擎」的协作要靠实测验证，不测 mock 出来的数据库

### 阶段验收清单

- [ ] 能写参数化查询：JDBC `PreparedStatement` + `setXxx` + `getGeneratedKeys` 回填主键，能说清为什么防注入（3.1、examples/ex01、exercises 练习 1）
- [ ] 能处理事务：`setAutoCommit(false)` / `commit` / `rollback` 三步到位，事务边界由业务定义，失败整体回滚（3.2、examples/ex02、exercises 练习 2）
- [ ] 能用连接池：HikariCP 配置与借还复用心智，能解释 `poolStats()` 的三个数字（3.3、examples/ex03、exercises 练习 3）
- [ ] 能设计基础缓存策略：Cache-Aside 先查缓存、未命中回源回填、TTL 兜底（3.5、examples/ex05、exercises 练习 4）
- [ ] 能诊断慢查询：`EXPLAIN PLAN FOR` 看执行计划，说出全表扫描与走索引的区别，能权衡索引的读写成本（3.4、examples/ex04、exercises 练习 5）
- [ ] 能说清 MyBatis 与 JPA 的分工与取舍，能用 Flyway 做版本化迁移（3.6/3.7、examples/ex06/ex07）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续：

- **用户表 CRUD**（★）：HSQLDB 内存库做参数化 CRUD + 业务校验 + 唯一约束兜底（对应 Roadmap 练习「用户表 CRUD」）
- **事务转账**（★★）：扣款 + 收款事务，余额不足与收款方不存在都要回滚（对应「事务转账」）
- **连接池**（★★）：HikariCP 池化 + 并发写，实测物理连接数不超过池上限（对应「连接池」）
- **Redis 缓存**（★★）：Cache-Aside + TTL，用本机 redis-server 实测（对应「Redis 缓存」）
- **慢查询优化**（★★★）：造数 + 执行计划对照 + 计时对比，量化索引收益（对应「慢查询优化」）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**学生管理数据库版**——把 ph12 的用户服务升级为连接池 + Flyway 迁移 + 事务批量导入 + 索引查询的完整数据库应用，纯 Java SE + HSQLDB + HikariCP。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`mvn test` 全绿 + 能解释事务回滚与索引计划的实测输出）

### 下一阶段

[ph14 Web 后端开发阶段](../ph14-web-backend/14-web-backend.md) — 本阶段 JDBC/事务/连接池/MyBatis/JPA 都是「裸 API 直连数据库」，ph14 把数据访问层接入 HTTP 服务：Servlet/Tomcat 讲清请求怎么进来、REST API/JSON 定接口形状、JWT 管「谁在调」、统一异常处理与日志把「能查库」升级为「能对外服务」——本阶段的存储层接口形状可平移为 ph14 的 `VehicleStore` 实现。
