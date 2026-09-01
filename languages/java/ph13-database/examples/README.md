# ph13 数据库 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，覆盖「JDBC 参数化 CRUD → 事务 → 连接池 → 索引与慢查询 → Redis 缓存 → MyBatis/Flyway → JPA/Hibernate」的完整链路。验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ HSQLDB 2.5.0**。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：本环境沙箱禁止写默认本地仓库 `~/.m2`（`Operation not permitted`），所需构件（hsqldb 2.5.0、HikariCP 5.0.1、jedis 3.9.0、mybatis 3.5.19、flyway-core 9.22.3、hibernate-core 6.5.3.Final、junit-jupiter 5.10.1 等）取自本地仓库缓存；沙箱内构建用 `mvn -o -Dmaven.repo.local=/tmp/m2clone`（把本地仓库指向可写目录的克隆）。**在正常联网环境直接执行 `mvn test` 即可**（首次运行会从 Maven Central 下载，之后走本地缓存）。

ex03/ex07 的 pom 里带了「离线版本仲裁」注释的依赖（slf4j-api、jakarta.xml.bind-api、jboss-logging、byte-buddy）：HikariCP 5.0.1 声明 slf4j-api 2.0.0-alpha1、Hibernate 6.5.3.Final 声明 jboss-logging 3.5.0.Final / byte-buddy 1.14.15 / jakarta.xml.bind-api 4.0.0，本机缓存缺声明的这些版本，用缓存内相近版本压过（机制见 ph11 主文档依赖仲裁）。**正常联网环境可删除这些项**，让依赖自行拉取声明版本。

## 示例列表

| 目录 | 验证状态 | 说明 | 测试命令（目录内） | 实测结果 |
|------|---------|------|-------------------|---------|
| ex01-jdbc-basics/ | ✅ 已验证 | JDBC 参数化 CRUD：自增主键回填 / Optional 映射 / 受影响行数 / UNIQUE 约束 / 防注入 | `mvn test` | Tests run: **4** |
| ex02-transaction-transfer/ | ✅ 已验证 | 事务转账：成功提交 / 余额不足回滚 / 收款方不存在回滚（rollback 语义实测） | `mvn test` | Tests run: **3** |
| ex03-hikari-pool/ | ✅ 已验证 | HikariCP 连接池：池化 CRUD / 连接复用（200 次借还 ≤ 4 条物理连接）/ 并发小池 | `mvn test` | Tests run: **3** |
| ex04-index-slowquery/ | ✅ 已验证 | 索引与慢查询：20000 行 + EXPLAIN PLAN FOR 对照 + 计时（无索引 78ms → 有索引 1ms） | `mvn test` | Tests run: **3** |
| ex05-redis/ | ✅ 已验证 | Redis：手写 RESP 客户端 + Jedis + Cache-Aside（需本机 redis-server） | `mvn test` | Tests run: **4**（2+2） |
| ex06-mybatis-flyway/ | ✅ 已验证 | MyBatis + Flyway 联调：版本化迁移 + Mapper 接口/XML + 自增回填 + 显式提交 | `mvn test` | Tests run: **3** |
| ex07-jpa-hibernate/ | ✅ 已验证 | JPA/Hibernate：实体注解映射 / 脏检查自动 UPDATE / JPQL | `mvn test` | Tests run: **3** |

## 验证记录（实测输出要点）

### ex01：JDBC 参数化 CRUD

- `mvn test` → `Tests run: 4, Failures: 0, Errors: 0, Skipped: 0`
- `RETURN_GENERATED_KEYS` 回填自增主键且主键递增；`findById(999L)` 返回 `Optional.empty`；`updateEmail(999L)` 返回 0 行
- **防注入实测**：插入 `x'); DROP TABLE users;--` 载荷后表安然无恙（`count()==1`），载荷被当纯数据存进 name 列

### ex02：事务转账

- `mvn test` → `Tests run: 3`
- **rollback 语义实测**：`missingPayee_rollsBackTheDebit` —— 扣款语句实际执行过，收款方不存在触发回滚，断言「没有回滚机制的话余额只剩 70」，实测余额分毫不变（100）
- 余额不足：`WHERE balance_cents >= ?` 条件让扣款影响 0 行，业务异常抛出，双方余额不变

### ex03：HikariCP 连接池

- `mvn test` → `Tests run: 3`
- **连接复用**：串行借还 200 次，`poolStats()` 显示物理连接总数 ≤ 4（池上限）
- **并发排队**：8 线程 × 25 次并发写、池上限 4，全部成功（池满时借连接排队等待）

### ex04：索引与执行计划

- `mvn test` → `Tests run: 3`；控制台输出 `[IndexLab] 20000 行 × 100 次等值查询: 无索引 78 ms, 有索引 1 ms`
- 无索引计划含 `access=FULL SCAN`；建索引后计划出现 `IDX_USERS_EMAIL`，不再全表扫描
- 计时对比同库同行数：先有索引计时、再 DROP 索引计时，公平对照

### ex05：Redis（需本机 redis-server）

- `mvn test` → `Tests run: 4`（RespClientTest 2 + JedisClientTest 2）
- `RedisServerHandle` 临时拉起端口 6399 的真实 redis-server（`--save ""` 不落盘），端口可连即就绪，测试结束优雅关闭
- TTL 语义实测：存在的键返回剩余秒数、不存在的键返回 -2
- **Cache-Aside 实测**：第一次未命中回源回填，删掉「数据库」后第二次仍命中——证明读的是缓存

### ex06：MyBatis + Flyway

- `mvn test` → `Tests run: 3`；控制台输出 Flyway `Successfully applied 2 migrations`
- `flyway_schema_history` 记录 V1（create users）/ V2（add email index），`success=true`
- MyBatis `useGeneratedKeys` 回填自增主键；JDBC 事务管理器下写操作必须显式 `session.commit()`

### ex07：JPA / Hibernate

- `mvn test` → `Tests run: 3`
- **脏检查实测**：托管对象改 `title` 字段、commit 时 Hibernate 自动生成 UPDATE（未调用任何 update 方法）
- JPQL `from Book where title like :kw` 面向对象查询，命中 `%Java%` 恰一条；`find(-1L)` 返回 null
