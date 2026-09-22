# ph13 数据库 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ HSQLDB 2.5.0 + JUnit Jupiter 5.10.1。本机 Maven 实测用 `mvn -o` 离线模式（沙箱禁止写默认本地仓库 `~/.m2`，依赖来自本地缓存 `/tmp/m2clone`）；正常联网环境直接 `mvn clean test` 即可。
> 五题与 Roadmap「ph13 数据库阶段」练习小节一一对应：用户表 CRUD / 事务转账 / 连接池 / Redis 缓存 / 慢查询优化。sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看；sol 文件是「源代码 + 注释里的完整 pom 与测试类」，建工程时按注释把 pom 与测试类写入自己的工程。
> 练习 3 需要 HikariCP（pom 参考 [../examples/ex03-hikari-pool/pom.xml](../examples/ex03-hikari-pool/pom.xml) 的「离线版本仲裁」注释），练习 4 需要本机安装 redis-server 与 Jedis（pom 参考 [../examples/ex05-redis/pom.xml](../examples/ex05-redis/pom.xml)），练习 1/2/5 只需 hsqldb（纯 Java 内存库，离线可用）。

## 练习 1：用户表 CRUD（★）

**目标**：用 JDBC 参数化查询实现用户表完整 CRUD，业务校验与数据库约束分层兜底——JDBC 基本功的总检验。
**要求**：

- 实现 `com.example.CrudUserDao`（构造器接收 `Connection`），建表 `users(id IDENTITY 主键, name NOT NULL, email NOT NULL UNIQUE)`
- `save(name, email)`：姓名 `null`/空白抛 `IllegalArgumentException`（Java 层快速失败），返回数据库生成的自增主键；`findById` 返回 `Optional<User>`；`findByEmail` 按邮箱查；`updateName` / `delete` 返回受影响行数；`count` 统计行数
- 全部写路径走 `PreparedStatement`；`@BeforeEach` 清表保证测试隔离

**验收**：`mvn test` 全部通过（参考实现实测 `Tests run: 5`）；测试覆盖：空白姓名拒绝、保存后按 id 查回、按邮箱命中/未命中、重复邮箱被 UNIQUE 约束拒绝、update/delete 受影响行数。

## 练习 2：事务转账（★★）

**目标**：实现扣款 + 收款两步事务，任何一步失败整体回滚——事务边界由业务定义的实战。
**要求**：

- 实现 `com.example.TransferAccount`（构造器接收 `Connection`）：`open(owner, balanceCents)` 开户、`balanceCents(id)` 查余额、`transferCents(fromId, toId, amountCents)` 转账
- `transferCents`：`setAutoCommit(false)` 开始事务 → 扣款（`WHERE balance_cents >= ?` 守余额底线，影响 0 行抛 `IllegalStateException`）→ 收款（账户不存在影响 0 行抛异常）→ 全部成功 `commit()`；任何异常 `rollback()` 后重抛；`finally` 恢复 autoCommit
- 金额单位用「分」（`long`），不用浮点数——金钱计算禁止 double/float

**验收**：`mvn test` 全部通过（参考实现实测 `Tests run: 3`）；三个用例：成功转账双方余额正确、余额不足双方余额分毫不变、收款方不存在时**扣款已执行但被回滚**（rollback 语义的直接证据）。

## 练习 3：连接池（★★）

**目标**：用 HikariCP 把裸 JDBC 升级为池化访问，实测「借还复用」与「并发排队」两个池心智。
**要求**：

- 实现 `com.example.PooledTaskDao`（HikariCP 驱动，`maximumPoolSize` 可配，实现 `AutoCloseable`）：建表、`insert`、`count`、`clear`，每次操作从池借连接、try-with-resources 归还
- 实现 `poolStats()` 返回 `total/active/idle`（读 `HikariDataSource.getHikariPoolMXBean()`）
- 测试覆盖：池化 CRUD 正常、**串行借还 200 次后物理连接总数 ≤ 池上限**（复用的直接证据）、**8 线程并发写池上限 4 全部成功**（池满排队）

**验收**：`mvn test` 全部通过（参考实现实测 `Tests run: 3`）；能解释「为什么 200 次操作不建 200 条连接」与「小池扛大流量的机制是排队」。

## 练习 4：Redis 缓存（★★）

**目标**：用本机 redis-server 做一次真实的 Redis 缓存（Cache-Aside），理解缓存旁路与 TTL 兜底——需要本机安装 redis-server。
**要求**：

- 测试类 `@BeforeAll` 用 `ProcessBuilder` 临时拉起独立端口（如 6399）的 `redis-server`（`--save "" --appendonly no --daemonize no`），轮询端口可连即就绪，`@AfterAll` 关闭；`redis-server` 不在 PATH 时测试如实报错（参考 [../examples/ex05-redis/src/test/java/com/example/RedisServerHandle.java](../examples/ex05-redis/src/test/java/com/example/RedisServerHandle.java)）
- 用 Jedis 实现 Cache-Aside 读：先 `get` 缓存，未命中回源（模拟数据库的 `Map`）并 `setex(key, 60, value)` 回填
- 测试覆盖：SET/GET/DEL 往返、**缓存命中时删掉「数据库」仍能读到值**（证明读的是缓存）、TTL 语义（存在的键 >0、不存在的键 = -2）

**验收**：`mvn test` 全部通过（参考实现实测 `Tests run: 3`，含 `@BeforeAll` 起真实 redis-server）；能说出 Cache-Aside 三步（查缓存 → 未命中回源 → 回填带 TTL）。

## 练习 5：慢查询优化（★★★）

**目标**：造数据、看执行计划、计时对比，量化「索引把全表扫描变成 B+ 树定位」——慢查询优化的完整流程。
**要求**：

- 实现 `com.example.IndexLab`（构造器接收 `Connection`）：建表 `users(id, name, email)`；`seed(rows)` 用 `addBatch + executeBatch` 批量造数（关自动提交一次落盘）；`planFor(sql)` 执行 `EXPLAIN PLAN FOR` 返回计划文本；`timeEmailLookup(email, times)` 返回 n 次等值查询总耗时（毫秒）；`createEmailIndex()` / `dropEmailIndex()`
- 测试按 `@Order` 共享同一张表（造数贵只做一次）：① 无索引时计划含 `FULL SCAN`；② 建索引后计划出现索引名、不再全表扫描；③ 计时对比：先有索引计时、DROP 后无索引计时，断言走索引更快
- 造 20000 行 × 100 次查询（参考 [../examples/ex04-index-slowquery](../examples/ex04-index-slowquery)）

**验收**：`mvn test` 全部通过（参考实现实测 `Tests run: 3`）；控制台打印实测毫秒数（本机 20000 行实测无索引 78ms、有索引 1ms，你的机器数值可能不同但方向必须一致），并能解释「为什么写入要付出索引维护成本」。
