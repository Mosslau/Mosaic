# Python 数据库与缓存阶段

> 面向自动化、Web 服务、车联网数据平台方向，本阶段用 SQL + SQLite 把数据层用透——建表、CRUD、事务、索引、迁移、连接池，再用 Redis 缓存查询结果，让"能开发完整业务系统"成为核心能力。

## 1. 概述

Python 数据库与缓存阶段的目标是：**能开发完整业务系统——用 SQL 建表与 CRUD、用事务保证一致性边界、用索引与查询计划优化读写、用迁移脚本追踪结构变更、用 Redis 缓存热点查询并设计过期与失效策略**。这一阶段把 ph10 的"能连数据库"深化为"能设计数据层"：SQLite 起步、SQL 优先，ORM 只做映射层；同时把四个必会概念内化为习惯——**SQL 基础比 ORM 更重要、迁移脚本让结构变更可追踪、事务保证一致性边界、缓存要有过期和失效策略**——这是并发（ph14）、部署（ph16）与车联网数据平台方向共同的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| SQL 基础 | DDL/DML/DQL、数据类型与约束、JOIN、聚合、参数化查询防注入 |
| SQLite 与关系型数据库 | `sqlite3` 标准库、事务与锁、迁移到 MySQL/PostgreSQL 的差异 |
| 事务与 ACID | `BEGIN`/`COMMIT`/`ROLLBACK`、原子性与一致性边界、失败回滚 |
| 索引与查询优化 | `CREATE INDEX`、`EXPLAIN QUERY PLAN`、B+ 树、避免全表扫描 |
| 迁移与连接池 | `schema_version` 手写迁移、Alembic 入门、连接复用与池参数 |
| Redis 缓存 | 数据类型与命令、`EXPIRE`/`TTL` 过期、LRU 淘汰、缓存失效策略 |

**范围边界**：本阶段承接 ph10 Web 后端——把"能连数据库"深化为"能设计完整数据层"：SQL 优先、事务、索引、迁移、连接池、Redis 缓存；不涉及并发与异步深入（ph14：大规模异步、消息队列）、部署运维（ph16：Nginx、Docker、CI/CD）；pymongo/motor 仅作可选了解，不深入 NoSQL 文档模型；本阶段以 SQLite 起步、SQL 优先，ORM 只做映射层。

## 2. 来源与演变

数据库技术经历了"关系模型标准化 → 开源服务分化 → 内存缓存补位"三次演进。**关系模型（Relational Model）** 1970 年由 Edgar F. Codd 提出，1979 年出现第一个商业产品 Oracle；**SQL 标准**从 1986 年的 SQL-86 起步（1987 年成为 ISO 标准），SQL-92 奠定了今天所有数据库共用的语法基线，SQL:1999 加入触发器、递归查询等特性。开源侧形成两强：**MySQL**（1995，MySQL AB）以"简单、快、生态大"取胜，**PostgreSQL**（1996，源自加州大学伯克利分校的 Postgres 研究项目）以"功能全、标准合规"著称，两者加上 **SQLite** 构成关系型数据库的三条主流路线。

**SQLite**（2000，D. Richard Hipp）走了一条完全不同的路：**嵌入式、零配置、文件即数据库**——不需要服务器进程，一个 `.db` 文件就是一个完整数据库；2004 年的 3.0 重写了存储引擎，2010 年的 3.7 引入 **WAL（Write-Ahead Logging，预写日志）** 模式改善读写并发。Python 生态同期补齐工具链：**SQLAlchemy**（2005，Mike Bayer）成为事实标准 ORM，2011 年配套的 **Alembic** 把"改表结构"变成可版本化的迁移脚本；而**缓存**的缺口由 **Redis**（2009，Salvatore Sanfilippo）补上——内存键值存储、单线程模型、支持过期与多种淘汰策略，成为"缓存查询结果"的标准答案。

| 时间 | 里程碑 |
|------|-------|
| 1986-1987 | SQL-86/SQL-87：首个 SQL 标准；1992 年 SQL-92 成为通用基线 |
| 1995-1996 | MySQL 与 PostgreSQL 相继发布，开源关系数据库两强 |
| 2000 | SQLite 1.0 发布（D. Richard Hipp）——嵌入式零配置数据库 |
| 2004 | SQLite 3.0——重写存储引擎（B-tree 存储、类型亲和） |
| 2005 | SQLAlchemy 发布（Mike Bayer），Python 事实标准 ORM |
| 2009 | Redis 发布——内存键值存储，缓存事实标准 |
| 2010 | SQLite 3.7 引入 WAL 模式，读写并发能力大幅提升 |
| 2011 | Alembic 发布——数据库迁移工具，与 SQLAlchemy 配套 |

## 3. 语法与参数

### 3.1 SQL 基础（DDL·DML·DQL·约束·参数化）

**SQL（Structured Query Language，结构化查询语言）** 按用途分三类：**DDL**（数据定义，`CREATE`/`ALTER`/`DROP`）、**DML**（数据操作，`INSERT`/`UPDATE`/`DELETE`）、**DQL**（数据查询，`SELECT`）。建表时用**约束（Constraint）** 把规则写进数据库：`PRIMARY KEY` 主键、`UNIQUE` 唯一、`NOT NULL` 非空、`FOREIGN KEY` 外键、`DEFAULT` 默认值。

```python
import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (        -- DDL：建表
    id INTEGER PRIMARY KEY,                              -- 自增主键
    name TEXT NOT NULL,                                  -- 非空约束
    email TEXT UNIQUE,                                   -- 唯一约束
    city TEXT DEFAULT 'Beijing'                          -- 默认值
)""")
cur.execute("INSERT INTO users (name, email) VALUES (?, ?)",  # DML：参数化占位符
            ("Alice", "alice@example.com"))
cur.execute("SELECT name, email FROM users WHERE city = ?",   # DQL：条件查询
            ("Beijing",))
print(cur.fetchall())                                    # [('Alice', 'alice@example.com')]
cur.execute("""SELECT city, COUNT(*) AS cnt FROM users   -- 聚合：GROUP BY
               GROUP BY city ORDER BY cnt DESC""")
print(cur.fetchall())
```

要点：

- **参数化查询（Parameterized Query）** 是铁律：值永远用 `?` 占位传入，**绝不字符串拼接 SQL**——拼接是 SQL 注入（SQL Injection）的根源（ph10 示例 4 用 `IntegrityError` 转 409 同理，先校验再入参）。
- **关联与聚合**：`JOIN` 把多张表按关联字段拼起来（`LEFT JOIN` 保留左表全量），`GROUP BY` + 聚合函数（`COUNT`/`SUM`/`AVG`）做分组统计——车辆状态按设备分组统计在线时长就是这种查询。
- **坑（忘记 WHERE）**：`UPDATE`/`DELETE` 不带 `WHERE` 会作用全表——先 `SELECT` 验证条件再执行写操作。

### 3.2 sqlite3 标准库 API（连接·游标·行工厂）

**`sqlite3` 是 Python 标准库**（零安装），API 三件套：`connect()` 建连接、`cursor()` 取游标、`execute()` 执行 SQL。`row_factory = sqlite3.Row` 让行支持按列名访问（像 dict 一样）。

```python
import sqlite3
conn = sqlite3.connect("app.db")
conn.row_factory = sqlite3.Row                # 行按列名访问
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)""")
cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Bob", "bob@example.com"))
print("lastrowid:", cur.lastrowid)            # 刚插入行的主键
conn.executemany("INSERT INTO users (name, email) VALUES (?, ?)",
                 [("C1", "c1@e.com"), ("C2", "c2@e.com")])   # 批量插入
conn.commit()                                 # 不 commit 不落盘！
row = cur.execute("SELECT * FROM users WHERE name = ?", ("Bob",)).fetchone()
print(row["email"])                           # Row 支持列名下标
print("总行数:", cur.execute("SELECT COUNT(*) FROM users").fetchone()[0])
```

要点：

- **`commit()` 才落盘**：`execute` 只是把 SQL 送进事务，不提交重启即丢；`with sqlite3.connect(...) as conn:` 上下文管理器会在成功时自动提交、异常时自动回滚（但**不会关闭连接**，见 3.4）。
- 常用读取 API：`fetchone()`/`fetchall()`/`fetchmany(n)`；写操作看 `cur.rowcount` 影响行数、`lastrowid` 新主键。
- **坑（连接跨线程）**：默认连接同一时刻只允许一个线程使用，多线程要 `check_same_thread=False` 并自行加锁（ph10 已用 `connect_args` 传过）。

### 3.3 SQLAlchemy Core 与 ORM（SQL 优先，ORM 只做映射层）

**SQL 基础比 ORM 更重要**（roadmap 必会概念）：ORM 的全部能力都是"生成 SQL"，看不懂 SQL 就调不好 ORM——`EXPLAIN` 查出来的慢查询、事务边界、索引选择，最终都要回到 SQL 层解决。SQLAlchemy 提供两层：**Core** 是"SQL 表达式 + 连接管理"（贴近 SQL），**ORM** 是"对象 ↔ 行"映射（ph10 已用 `Mapped`/`mapped_column`/`Session` 写过）。

```python
# 依赖：pip install sqlalchemy（本机未安装，仅展示写法；示例均用标准库等价实现）
from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///app.db")
with engine.connect() as conn:
    rows = conn.execute(text("SELECT * FROM users WHERE city = :c"), {"c": "Beijing"})
    print(rows.fetchall())
```

要点：

- **会读 ORM 生成的 SQL**：打开 echo（`create_engine(url, echo=True)`）能看到每条语句，这是排查 N+1、走没走索引的第一步（ph10 3.7 的 N+1 坑在此闭环）。
- Core 与 ORM 同源：ORM 查询最终也是生成 Core 表达式再编译成 SQL；连接池、事务、迁移由引擎统一管理。
- 本阶段"SQL 优先"的落法：**先会写 SQL，再用 ORM 减少样板**——示例 1/3 用标准库把 SQL 本身练透，示例 4 展示迁移脚本；SQLAlchemy 的具体 API 在 ph10 已入门，这里强调其背后就是 SQL。

### 3.4 事务与 ACID（BEGIN·COMMIT·ROLLBACK）

**事务（Transaction）** 把一组操作包成一个原子单位：要么全部成功（`COMMIT`），要么全部不生效（`ROLLBACK`）。**事务保证一致性边界**（roadmap 必会概念）——"转账：A 扣钱 + B 加钱"必须同生共死，否则 A 扣了 B 没加就是数据不一致。

```python
import sqlite3
conn = sqlite3.connect("bank.db")
conn.isolation_level = None              # 关闭隐式事务：BEGIN/COMMIT/ROLLBACK 全手动
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, name TEXT, balance REAL)")
cur.execute("BEGIN")                     # 显式开启事务
try:
    cur.execute("UPDATE accounts SET balance = balance - 100 WHERE name = 'A'")
    cur.execute("COMMIT")                # 全部成功 → 落盘
except Exception:
    cur.execute("ROLLBACK")              # 任一步失败 → 全部撤销
    raise
```

要点：

- **ACID 四特性**：**原子性**（Atomicity，要么全成要么全无）、**一致性**（Consistency，约束与业务规则不被破坏）、**隔离性**（Isolation，并发事务互不干扰，见 4.3）、**持久性**（Durability，提交后不因崩溃丢失）。
- `sqlite3` 默认 `isolation_level=""`：`INSERT`/`UPDATE`/`DELETE` 前自动 `BEGIN`，`commit()` 才结束——**每个写操作后都要 commit**，否则数据"看似成功实则丢失"（ph10 已踩过这个坑）。
- 手动事务用 `isolation_level = None` + 显式 `BEGIN`（示例 2 完整演示失败回滚）；嵌套事务用 `SAVEPOINT`（`conn.execute("SAVEPOINT sp")` / `RELEASE sp`）。

### 3.5 索引（CREATE INDEX·EXPLAIN QUERY PLAN·最左前缀）

**索引（Index）** 是数据库为加速查询建立的"目录"：没有它，`WHERE` 只能**全表扫描（Full Table Scan）**，百万行表一条查询就是百万次比较；有了索引，查询走 B+ 树按需定位（原理见 4.1）。

```python
import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT)")
cur.execute("INSERT OR IGNORE INTO users (email) VALUES ('alice@example.com')")
conn.commit()
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'alice@example.com'")
print(cur.fetchall())                    # 无索引：SCAN users（全表扫描）
cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'alice@example.com'")
print(cur.fetchall())                    # 有索引：SEARCH ... USING COVERING INDEX idx_users_email
```

要点：

- **`EXPLAIN QUERY PLAN` 是 SQLite 的"体检报告"**：看到 `SCAN` 就该考虑加索引，看到 `SEARCH ... USING INDEX` 说明索引生效（示例 3 对比实测耗时）。
- **索引不是越多越好**：每多一个索引，写入就多维护一份（写放大），小表、写多读少、频繁更新的列都不该加；索引是**空间换时间**。
- **复合索引（Composite Index）按最左前缀（Leftmost Prefix）生效**：`(city, status)` 索引能加速 `WHERE city=?` 和 `WHERE city=? AND status=?`，但**不能**加速只按 `status` 的查询——列顺序即前缀顺序。

### 3.6 连接池（Connection Pool·池参数）

**连接池（Connection Pool）** 是"连接的复用仓库"：建立数据库连接是昂贵操作（TCP 握手 + 认证 + 内存分配），每次请求新建、用完销毁太浪费；连接池预先建好一批连接，请求来了**借**、用完**还**，超出的请求排队等待（原理见 4.4）。

```python
# 依赖：pip install sqlalchemy pymysql（未安装，仅展示配置写法；MySQL 场景）
from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://user:pass@host/db",
                       pool_size=5,          # 池内常驻连接数
                       max_overflow=10,      # 高峰期最多再开 10 条
                       pool_recycle=3600,    # 连接超过 1 小时回收重建
                       pool_pre_ping=True)   # 借出前 ping 验证连接存活
```

要点：

- **池是"复用"，不是"无限开"**：`pool_size + max_overflow` 是连接上限，超过就阻塞等待——连接泄漏（借了不还）会慢慢把池占满，最终全部请求超时（ph10 的"Session 用完必须关"就是防这个）。
- **`pool_pre_ping=True` 防"失效连接"**：数据库重启、网络抖动后池里的旧连接已死，借出前 ping 一下能避免"拿到手就用不了"。
- **SQLite 的特殊性**：连接极廉价（就是打开一个文件）且文件锁语义特殊，SQLAlchemy 对**文件型 SQLite 默认用 NullPool**（不池化，每会话新连接），连接池主要服务于 MySQL/PostgreSQL 这类服务器型数据库。

### 3.7 Redis 数据类型与命令（string·hash·list·set·zset·过期）

**Redis** 是内存键值存储（In-Memory Key-Value Store）：数据存在内存里，读写是微秒级，比查磁盘数据库快两三个数量级——典型用法是把**热点查询结果**缓存起来（查询先看缓存，命中即返回，未命中查库再回填）。核心是五种数据类型 + 过期机制：

| 类型 | 示例命令 | 用途 |
|------|---------|------|
| string | `SET`/`GET`/`SETEX` | 缓存 JSON 字符串、计数器（`INCR`） |
| hash | `HSET`/`HGETALL` | 存对象字段（设备信息） |
| list | `LPUSH`/`LRANGE` | 消息队列、最近列表 |
| set | `SADD`/`SISMEMBER` | 去重、标签集合 |
| zset | `ZADD`/`ZRANGEBYSCORE` | 排行榜、按分数排序 |

```bash
# redis-cli 命令（需要 redis-server；过期与淘汰是缓存设计的核心）
SET device:1001 '{"vin":"V001","online":true}' EX 300   # 5 分钟过期（TTL）
GET device:1001
EXPIRE device:1001 60                                     # 动态调整过期
TTL  device:1001                                          # 查剩余秒数（-1 永不过期）
```

```python
# 依赖：pip install redis + 本地 redis-server（未安装；示例 5 用纯 Python 模拟同一思路）
import redis
r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
r.setex("device:1001", 300, '{"vin":"V001"}')   # 写缓存 + 过期时间
data = r.get("device:1001")                     # 命中返回字符串，未命中返回 None
```

要点：

- **缓存要有过期和失效策略**（roadmap 必会概念）：`EXPIRE`/`TTL` 管**过期**（数据变旧就失效），`maxmemory-policy` 管**淘汰**（内存满时按策略腾位置，`allkeys-lru` 淘汰最久未用）；再配合**主动失效**（写库时同步删/更新缓存）——三个机制缺一不可，详见 4.5 与示例 5。
- **pymongo/motor 可选**：MongoDB 是文档型 NoSQL（存 JSON 文档、无表结构），roadmap 仅列为了解项——本阶段不深入，先把关系型 + 缓存练透。
- 生产注意：缓存 key 要有统一命名（如 `device:{id}`），value 一般是序列化后的 JSON（配合 ph10 的 Pydantic `model_dump`）。

## 4. 底层原理

### 4.1 B+ 树索引（为什么索引快）

索引的数据结构是 **B+ 树（B+ Tree）**：一种多路平衡查找树，所有数据都存在**叶子节点**，内部节点只存"键 + 指针"用来路由。一棵树的节点按**页（Page）** 存储（SQLite 默认 4KB/页），每页能装几十上百个键，所以**树高很矮**——百万行数据的索引树通常只有 3-4 层：查一次索引 = 3-4 次磁盘页读取，而全表扫描 = 百万次页读取，这就是索引快几个数量级的原理。表的主键（`INTEGER PRIMARY KEY`）在 SQLite 里是**聚簇索引（Clustered Index）**：数据行直接存在主键树的叶子页上；普通索引（二级索引）的叶子只存"索引键 + 主键值"，命中后还要按主键**回表（Table Lookup）** 取整行——如果查询需要的列全在索引里，就能**覆盖索引（Covering Index）** 免回表，这是"索引里多放一列"能加速的秘密。

### 4.2 事务的 WAL 与回滚日志（SQLite 的持久化与崩溃恢复）

SQLite 用两种日志保证事务的**持久性与原子性**。默认的 **rollback journal 模式**（`journal_mode=DELETE`）写的是"回滚日志"：事务开始先把将改动的旧页副本写进日志文件，再改数据库页，全部成功后才把日志删除——崩溃时若日志还在，就用日志把数据库**还原到事务前**（回滚），保证"要么全成、要么全无"。**WAL（Write-Ahead Logging，预写日志）模式**（`PRAGMA journal_mode=WAL`，3.7.0 起）换了个思路：改动**先追加写进独立的 `-wal` 日志文件**，再在合适时机（checkpoint）合并回主库文件——这样读事务只读主库快照、写事务只追加日志，**读者不阻塞写者**，并发能力大幅提升；崩溃恢复时重放 WAL 即可。两种模式都依赖 `fsync` 把日志真正刷到磁盘——"提交成功" = 日志已落盘，这是持久性的物理保证。

### 4.3 隔离级别（并发事务的四种边界）

**隔离性（Isolation）** 处理"多个事务同时读写同一批数据"时的干扰，标准定义了四种**隔离级别（Isolation Level）**，从松到严：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| 读未提交（Read Uncommitted） | 可能 | 可能 | 可能 |
| 读已提交（Read Committed） | 避免 | 可能 | 可能 |
| 可重复读（Repeatable Read） | 避免 | 避免 | 可能 |
| 串行化（Serializable） | 避免 | 避免 | 避免 |

**脏读（Dirty Read）** 是读到别人未提交的数据（可能被回滚）；**不可重复读（Non-Repeatable Read）** 是同一事务两次读同一行结果不同（别人改了并提交）；**幻读（Phantom Read）** 是同一事务两次范围查询多出/少了行。**SQLite 默认就是串行化**：整个数据库单写者 + 锁控制，天然没有脏读幻读（代价是写并发受限，WAL 缓解读阻塞）；**PostgreSQL 默认读已提交**（每语句快照），**MySQL InnoDB 默认可重复读**（事务快照）。工程上"事务边界"的选择就是在这张表上权衡：要强一致选串行化/可重复读，要高并发容忍一点弱隔离。

### 4.4 连接池原理（借·还·失效）

连接池本质是"**有限连接的出借队列**"（SQLAlchemy 的 `QueuePool`）：池初始化创建 `pool_size` 条连接排好队；请求来取连接（借出），用完归还（还池）；池空了且有 `max_overflow` 余量就临时新建，**超过上限则调用方阻塞等待**（可配 `timeout` 抛超时错误）。三个工程细节：一是**连接会失效**——数据库重启、网络中断后池里"看起来活着"的连接实际已死，`pool_pre_ping` 在借出前发一个轻量探活；二是**连接要回收**——`pool_recycle` 定期重建连接，规避服务端空闲超时断开和内存累积；三是**会话（Session）≠ 连接**——SQLAlchemy 里 Session 是"工作单元"（ph10 4.4），它按需从池里借连接、事务结束归还——所以"会话泄漏"的真相是**连接借了没还**，池被占满后所有新请求排队饿死。

### 4.5 Redis 单线程事件循环与持久化（为什么快·怎么不丢）

Redis **命令执行是单线程的**：一个进程用**事件循环（Event Loop，epoll）** 处理所有客户端连接，同一时刻只有一条命令在跑。单线程看似慢，实则快：**数据全在内存**（无磁盘 I/O）、**命令天然原子**（无锁、无上下文切换、无竞争）；代价是**单条命令必须快**——`KEYS *`、大键遍历这类 O(N) 命令会阻塞整个服务，生产禁用。持久化两条路：**RDB**（定时把内存快照 fork 子进程写盘，恢复快、可能丢最近一次快照后的数据）与 **AOF**（把每条写命令追加到日志，`appendfsync` 策略控制刷盘频率，最多丢 1 秒数据）；两者可同时开启。**过期与淘汰**：Redis 对带 TTL 的键用"**惰性删除**（访问时发现过期即删）+ **定期删除**（周期抽样清理）"双策略；内存达到 `maxmemory` 后按 `maxmemory-policy` 淘汰，`allkeys-lru` 是最常用的"近似 LRU"。缓存的三大坑由此展开：**穿透**（查不存在的 key 每次都打库——对策：空值也缓存 + 布隆过滤器）、**击穿**（热点 key 过期瞬间打爆库——对策：互斥锁重建）、**雪崩**（大量 key 同时过期——对策：随机 TTL + 多级缓存）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 用户 CRUD | sqlite3 建表 + 增删改查 + 参数化查询 + 唯一约束 |
| 设备信息管理 | vin 唯一约束 + 索引 + 迁移脚本加字段（如 `online` 状态） |
| 车辆状态表 | 高频写入 + 按设备/时间查询 + 复合索引（`(device_id, ts)`） |
| 热点查询缓存 | Redis string 缓存查询结果 + TTL 过期 + 失效策略 |
| 事务型业务（订单/转账） | BEGIN/COMMIT/ROLLBACK + 一致性边界 + 失败回滚 |
| 数据平台后端 | SQLAlchemy + Alembic 迁移 + 连接池 + Redis 缓存（承接 ph10） |

**不适合此阶段的事项**：

- 大规模异步与消息（Kafka、MQ、百万级并发连接）：ph14 并发阶段
- 生产部署（Nginx、Docker、K8s、CI/CD、监控告警）：ph16 部署阶段
- NoSQL 文档模型深入（MongoDB 聚合、分片）：本阶段 pymongo/motor 仅可选了解
- 分布式事务、分库分表、读写分离：单库起步的业务系统先不涉及，ph16 部署阶段再谈

## 6. 代码示例

本节 5 个示例全部用**标准库 `sqlite3` 实现**（本机 Python 3.9 已内置，可直接运行；sqlalchemy/redis/alembic 未安装，对应能力给出替代实现并注明）。示例会在当前目录生成 `app.db`/`bank.db`/`perf.db`/`migrate.db`，可随时删除重建。

### 示例 1：用户 CRUD（标准库 sqlite3，对应 roadmap 示例）

对应 roadmap 示例的完整版：建表 + 增删改查 + 参数化查询 + 唯一约束冲突处理。

```python
import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE
)""")
cur.execute("DELETE FROM users")                          # 清空旧数据，保证可重复运行
cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Alice", "alice@example.com"))
conn.commit()
print(cur.execute("SELECT * FROM users WHERE name = ?", ("Alice",)).fetchone())
cur.execute("UPDATE users SET name = ? WHERE email = ?", ("Alice2", "alice@example.com"))
cur.execute("DELETE FROM users WHERE email = ?", ("alice@example.com",))
conn.commit()
print("剩余用户数:", cur.execute("SELECT COUNT(*) FROM users").fetchone()[0])
try:                                                      # 唯一约束冲突
    cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Dup", "dup@e.com"))
    cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Dup2", "dup@e.com"))
    conn.commit()
except sqlite3.IntegrityError as e:
    conn.rollback()                                       # 冲突后事务要回滚
    print("唯一约束生效:", e)
```

要点：写操作后必须 `commit()`；重复插入同 email 会抛 `sqlite3.IntegrityError`，捕获后**记得 `rollback()`**，否则后续操作都在一个坏事务里（对应 ph10 的 `IntegrityError → 409`）。把 `INSERT`/`SELECT`/`UPDATE`/`DELETE` 各包一个函数（`create_user`/`get_user`/`update_user`/`delete_user`）就是完整 CRUD 服务，可直接被 ph10 的 FastAPI 路由调用。

### 示例 2：事务与失败回滚（转账）

演示"事务保证一致性边界"：余额不足时整个转账**原子回滚**，两边余额都不变。

```python
import sqlite3
conn = sqlite3.connect("bank.db")
conn.isolation_level = None                     # 手动控制事务
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, name TEXT, balance REAL)")
cur.execute("DELETE FROM accounts")
cur.execute("INSERT INTO accounts (name, balance) VALUES ('A', 1000)")
cur.execute("INSERT INTO accounts (name, balance) VALUES ('B', 0)")

def transfer(frm: str, to: str, amount: float):
    cur.execute("BEGIN")
    try:
        bal = cur.execute("SELECT balance FROM accounts WHERE name = ?", (frm,)).fetchone()[0]
        if bal < amount:
            raise ValueError(f"{frm} 余额不足: {bal}")
        cur.execute("UPDATE accounts SET balance = balance - ? WHERE name = ?", (amount, frm))
        cur.execute("UPDATE accounts SET balance = balance + ? WHERE name = ?", (amount, to))
        cur.execute("COMMIT")
        print(f"转账成功: {frm} -> {to} {amount}")
    except Exception as e:
        cur.execute("ROLLBACK")
        print(f"转账失败已回滚: {e}")

transfer("A", "B", 2000)                        # 失败：余额不足 → 整笔回滚
transfer("A", "B", 300)                         # 成功
for row in cur.execute("SELECT name, balance FROM accounts ORDER BY id"):
    print(row)                                  # A=700, B=300（第一次的 2000 没生效）
```

要点：`BEGIN` 到 `COMMIT` 之间是**一致性边界**——两条 `UPDATE` 要么都生效要么都不生效；失败的转账（余额不足）走 `ROLLBACK`，A 的余额保持不变。这正对应 roadmap 必会概念"事务保证一致性边界"；真实项目里这个边界通常由 ORM Session 管理（ph10 的 `session.commit()`/`session.rollback()` 就是同一件事）。

### 示例 3：索引与查询优化（EXPLAIN QUERY PLAN + 实测耗时）

两万行数据按 vin 精确查询：先看全表扫描的执行计划与耗时，加索引后再对比。

```python
import sqlite3, time
conn = sqlite3.connect("perf.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS devices (id INTEGER PRIMARY KEY, vin TEXT, model TEXT, online INTEGER)")
cur.execute("DELETE FROM devices")
cur.executemany("INSERT INTO devices (vin, model, online) VALUES (?, ?, ?)",
                [(f"VIN{i:06d}", f"EV-{i % 5}", i % 2) for i in range(20000)])
conn.commit()

print("--- 无索引 ---")
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM devices WHERE vin = 'VIN000123'")
print(cur.fetchall())                            # ('SCAN devices',) 全表扫描
t0 = time.perf_counter()
cur.execute("SELECT * FROM devices WHERE vin = 'VIN000123'").fetchall()
print(f"耗时: {(time.perf_counter() - t0) * 1000:.2f} ms")

cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_vin ON devices(vin)")
conn.commit()
print("--- 有索引 ---")
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM devices WHERE vin = 'VIN000123'")
print(cur.fetchall())                            # SEARCH ... USING INDEX idx_devices_vin
t0 = time.perf_counter()
cur.execute("SELECT * FROM devices WHERE vin = 'VIN000123'").fetchall()
print(f"耗时: {(time.perf_counter() - t0) * 1000:.2f} ms")
```

要点：执行计划从 `SCAN` 变为 `SEARCH ... USING INDEX`，耗时下降（数据量再大一个数量级时差距更明显）；**判断"要不要索引"先跑 `EXPLAIN QUERY PLAN`**——这是"SQL 基础比 ORM 更重要"在性能上的落点。车辆状态表按 `(device_id, ts)` 建复合索引同理（3.5 最左前缀）。

### 示例 4：简易迁移脚本（schema_version 手写迁移）

alembic 未安装，这里用手写迁移脚本演示**同一套思想**：每个版本一段 SQL，按顺序执行，已执行版本记录在 `schema_version` 表里——**迁移脚本让结构变更可追踪**（roadmap 必会概念）。装好 alembic 后，这套逻辑由 `alembic revision --autogenerate` + `alembic upgrade head` 接管（ph10 3.7）。

```python
import sqlite3
conn = sqlite3.connect("migrate.db")
conn.isolation_level = None
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")

MIGRATIONS = [                                  # 版本号递增，只增不改
    (1, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"),
    (2, "ALTER TABLE users ADD COLUMN email TEXT"),
    (3, "CREATE INDEX idx_users_name ON users(name)"),
]

def current_version():
    return cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]

def migrate():
    for version, sql in MIGRATIONS:
        if version <= current_version():
            continue
        print(f"应用迁移 v{version}: {sql}")
        cur.execute("BEGIN")
        try:
            cur.execute(sql)
            cur.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))", (version,))
            cur.execute("COMMIT")
        except Exception as e:
            cur.execute("ROLLBACK")             # 迁移失败整体回滚，不留半成品结构
            raise RuntimeError(f"迁移 v{version} 失败: {e}") from e

migrate()
print("当前 schema 版本:", current_version())    # 3
migrate()                                        # 幂等：再跑一遍不会重复执行
print("再次执行后版本仍为:", current_version())
```

要点：**迁移 = 版本化的 SQL**——数据库结构从 v1 一步步升级到 v3，每个版本一条记录，可回放、可审计、可追踪（谁在什么时间把结构改成了什么样）；迁移在**事务里执行**，失败即回滚，不会留下"建了表但没记版本"的半成品。这是"迁移脚本让结构变更可追踪"的标准落地；Alembic 只是把这个框架工程化（`upgrade head`、`downgrade`、`autogenerate` 对比模型差异）。

### 示例 5：缓存策略演示（functools.lru_cache + 过期模拟）

redis-py 未安装，这里用 `functools.lru_cache` 演示缓存三要素：**命中（Hit）、过期（TTL）、淘汰（LRU）**——思路与 Redis 完全一致：`maxsize` 对应 `maxmemory` + `allkeys-lru` 淘汰，时间窗口参数对应 `EXPIRE`/`TTL` 过期。

```python
import functools, time

def query_user(user_id):
    """模拟慢查询（真实项目里是示例 1 的数据库 CRUD）"""
    time.sleep(0.3)
    return {"id": user_id, "name": f"user-{user_id}"}

TTL = 3                                        # 缓存有效期（秒），对应 Redis EXPIRE
@functools.lru_cache(maxsize=64)               # 对应 Redis maxmemory + allkeys-lru 淘汰
def _cached(user_id, window):
    return query_user(user_id)

def get_user(user_id):
    window = int(time.monotonic() // TTL)      # 每 TTL 秒一个窗口：窗口一变，旧缓存自动失效
    t0 = time.perf_counter()
    data = _cached(user_id, window)
    hit = "hit" if (time.perf_counter() - t0) < 0.05 else "miss"
    return data, hit

print(get_user(1))                             # miss：首次查库（0.3s）
print(get_user(1))                             # hit：命中缓存（毫秒级）
time.sleep(TTL + 0.5)                          # 超过有效期
print(get_user(1))                             # miss：缓存过期失效，重新查库
```

要点：`lru_cache` 的 `maxsize` + LRU 淘汰 ≈ Redis 的 `maxmemory-policy=allkeys-lru`，时间窗口参数 ≈ Redis 的 `EXPIRE`——**缓存要有过期和失效策略**（roadmap 必会概念），过期兜底"数据变旧"，淘汰兜底"内存放不下"。生产等价的 redis-py 写法（需 `pip install redis` + redis-server，未安装故不在此运行）：

```python
# import redis
# r = redis.Redis(decode_responses=True)
# data = r.get(f"user:{user_id}")              # 命中：直接返回
# if data is None:                             # 未命中：查库 → 回填 + 设过期
#     data = query_user(user_id)
#     r.setex(f"user:{user_id}", 300, json.dumps(data))
```

## 7. 总结

### 关键要点

1. **SQL 基础比 ORM 更重要**：ORM 只是生成 SQL 的映射层，`EXPLAIN QUERY PLAN`、事务边界、索引选择最终都在 SQL 层解决（roadmap 必会概念）
2. **迁移脚本让结构变更可追踪**：结构变更 = 版本化的 SQL，事务内执行、失败回滚、可重放——手写 `schema_version` 与 Alembic 是同一套思想（roadmap 必会概念）
3. **事务保证一致性边界**：`BEGIN`/`COMMIT`/`ROLLBACK` 让一组操作同生共死，失败必须回滚，否则半提交就是数据不一致（roadmap 必会概念）
4. **缓存要有过期和失效策略**：TTL 过期 + LRU 淘汰 + 主动失效三者缺一不可，穿透/击穿/雪崩各有对策（roadmap 必会概念）
5. **参数化查询是铁律**：值永远走占位符，绝不拼接 SQL——SQL 注入的防线在第一行代码
6. **`commit()` 才落盘**：忘 commit = 数据丢失；`IntegrityError` 后要 `rollback()`，否则坏事务污染后续操作
7. **索引是空间换时间**：`EXPLAIN QUERY PLAN` 看 `SCAN` 还是 `SEARCH`；复合索引最左前缀生效；写多读少不建索引
8. **连接池是"借还"不是"无限开"**：`pool_size`/`max_overflow`/`pool_recycle`/`pool_pre_ping`；会话泄漏 = 连接借了没还
9. **SQLite 串行化、MySQL/PostgreSQL 各有默认隔离级别**：隔离级别是并发与一致性的权衡表
10. **Redis 单线程也快**：内存 + 事件循环 + 命令原子；RDB/AOF 管持久化，`EXPIRE`/`maxmemory-policy` 管缓存生命周期

### 跨语言对比：数据库访问与缓存

| 维度 | Python | Java | Go | C++ |
|------|--------|------|----|-----|
| 驱动/标准库 | `sqlite3`（标准库）、psycopg2、PyMySQL | JDBC（`java.sql`） | `database/sql` + 驱动 | sqlite3（C 库）、libpq、mysql-connector-c++ |
| ORM | SQLAlchemy（Core+ORM） | Hibernate/JPA、MyBatis | GORM、ent、sqlx | ODB、自研封装 |
| 迁移工具 | Alembic | Flyway、Liquibase | golang-migrate、goose | 手工脚本为主 |
| 连接池 | SQLAlchemy QueuePool | HikariCP | `database/sql` 内置 | 自研/libpq 池 |
| 缓存客户端 | redis-py | Jedis、Lettuce、Spring Data Redis | go-redis | hiredis、redis-plus-plus |
| 生态特点 | SQLAlchemy 一家独大，标准库直接可用 | 企业规范（JPA）与 MyBatis 并存 | 标准库薄封装、手写 SQL 常见 | 无统一标准，多自研 |

### 阶段验收标准

- 能建表和 CRUD：`sqlite3` 建表 + 增删改查 + 参数化查询 + 唯一约束（对应 roadmap"能建表和 CRUD"）
- 能写迁移脚本：手写 `schema_version` 迁移或 Alembic，结构变更可版本化、可重放（对应 roadmap"能写迁移脚本"）
- 能设计基础缓存：TTL 过期 + LRU 淘汰 + 失效策略，能解释穿透/击穿/雪崩（对应 roadmap"能设计基础缓存"）
- 能解释四个必会概念：SQL 优先、迁移可追踪、事务一致性边界、缓存过期失效
- 能说明事务与索引原理：ACID、WAL/回滚日志、B+ 树、隔离级别、连接池借还

### 进入下一阶段前

确保能完成以下练习：

- 用户 CRUD：把示例 1 包成 `create_user`/`get_user`/`update_user`/`delete_user` 四个函数并跑通（提示：每个写操作后 `commit()`；重复 email 捕获 `IntegrityError` 后 `rollback()`）
- 设备信息管理：`devices` 表 + vin 唯一约束 + `CREATE INDEX`，用 `EXPLAIN QUERY PLAN` 验证按 vin 查询走索引（提示：复合索引注意最左前缀）
- 车辆状态表：`vehicle_status(device_id, ts, status)` 高频写入，用 `executemany` 批量插入，按 `(device_id, ts)` 建复合索引查询（提示：对比有/无索引的耗时，参考示例 3）
- Redis 缓存查询结果：把示例 5 的 `get_user` 换成 redis-py（`SETEX` + `GET`）在有 redis-server 的机器上跑通（提示：缓存 miss 时查库回填并设 TTL；写库后主动删缓存防脏读）
- 迁移脚本：给示例 4 的 `MIGRATIONS` 加一个 v4（如 `ALTER TABLE users ADD COLUMN city TEXT`）并重跑，确认只执行新版本（提示：用 `current_version()` 断点检查）

### 推荐项目

- **设备管理后端**：`devices` 表（vin 唯一索引）+ `device_status` 状态表（复合索引）+ 用户 CRUD + 手写迁移脚本演进结构 + Redis 缓存设备热点查询（呼应 roadmap"设备管理后端"；示例 1/3/4/5 的合体，也是 ph10 设备管理 API 的数据层升级）
- **车辆状态存储服务**：高频批量写入车辆状态（`executemany`）+ 按设备/时间范围查询（复合索引 + `EXPLAIN` 验证）+ 状态查询结果缓存（TTL 过期 + 失效策略）（呼应 roadmap"车辆状态存储服务"；车联网数据平台方向的核心数据服务）

### 下一阶段

**自动化脚本阶段**（ph12-automation，文档规划中）—— 文件批处理、Excel 自动化、日志分析、接口测试、报表生成、爬虫与定时任务、paramiko/fabric 远程操作；ph11 的数据库与缓存能力让脚本能安全地读写数据、批量入库、从库取数生成报表，爬虫抓取的数据也有了落库与去重的去处。
