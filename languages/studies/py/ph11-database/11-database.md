# Python 数据库与缓存阶段

> 面向自动化、Web 服务、数据平台方向，本阶段用 SQL + SQLite 把数据层用透——建表、CRUD、事务、索引、迁移、连接池，再用 Redis 缓存查询结果，让「能开发完整业务系统」成为核心能力。

## 1. 概述

Python 数据库与缓存阶段的目标是：**能开发完整业务系统——用 SQL 建表与 CRUD、用事务保证一致性边界、用索引与查询计划优化读写、用迁移脚本追踪结构变更、用 Redis 缓存热点查询并设计过期与失效策略**。这一阶段把 ph10 Web 后端阶段的「能连数据库」深化为「能设计数据层」：SQLite 起步、SQL 优先，ORM 只做映射层；同时把四个必会概念内化为习惯——**SQL 基础比 ORM 更重要、迁移脚本让结构变更可追踪、事务保证一致性边界、缓存要有过期和失效策略**——这是 [ph14 并发、并行与异步阶段](../ph14-concurrency-async/14-concurrency-async.md)（roadmap 第 14 节）、[ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）与数据平台方向共同的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| SQL 基础 | DDL/DML/DQL、数据类型与约束、JOIN、聚合、参数化查询防注入 |
| SQLite 与关系型数据库 | `sqlite3` 标准库、事务与锁、了解迁移到 MySQL/PostgreSQL 的差异方向 |
| 事务与 ACID | `BEGIN`/`COMMIT`/`ROLLBACK`、原子性与一致性边界、失败回滚 |
| 索引与查询优化 | `CREATE INDEX`、`EXPLAIN QUERY PLAN`、B+ 树、避免全表扫描 |
| 迁移与连接池 | `schema_version` 手写迁移、Alembic 入门、连接复用与池参数 |
| Redis 缓存 | 数据类型与命令、`EXPIRE`/`TTL` 过期、LRU 淘汰、缓存失效策略 |

这个阶段只涉及关系型数据库与缓存——SQL 与 SQLite、事务与 ACID、索引与查询优化、迁移与连接池、Redis 缓存，**不涉及并发与异步深入（Kafka、消息队列、大规模异步）和生产部署运维（Nginx、Docker、CI/CD）** — 那些是 [ph14 并发、并行与异步阶段](../ph14-concurrency-async/14-concurrency-async.md)（roadmap 第 14 节）和 [ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）的内容。NoSQL 文档模型（pymongo/motor）仅作可选了解，本阶段不深入。本阶段承接 ph10 Web 后端阶段——把「能连数据库」深化为「能设计完整数据层」：SQL 优先、事务、索引、迁移、连接池、Redis 缓存，以 SQLite 起步（正式项目换 PostgreSQL/MySQL 时，SQL 层能力直接平移）。本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

数据库技术经历了「关系模型标准化 → 开源服务分化 → 内存缓存补位」三次演进。**关系模型（Relational Model）** 1970 年由 Edgar F. Codd 提出，1979 年出现第一个商业产品 Oracle；**SQL 标准**从 1986 年的 SQL-86 起步（1987 年成为 ISO 标准），SQL-92 奠定了今天所有数据库共用的语法基线，SQL:1999 加入触发器、递归查询等特性。开源侧形成两强：**MySQL**（1995，MySQL AB）以「简单、快、生态大」取胜，**PostgreSQL**（1996，源自加州大学伯克利分校的 Postgres 研究项目）以「功能全、标准合规」著称，两者加上 **SQLite** 构成关系型数据库的三条主流路线。

**SQLite**（2000，D. Richard Hipp）走了一条完全不同的路：**嵌入式、零配置、文件即数据库**——不需要服务器进程，一个 `.db` 文件就是一个完整数据库；2004 年的 3.0 重写了存储引擎，2010 年的 3.7 引入 **WAL（Write-Ahead Logging，预写日志）** 模式改善读写并发。Python 生态同期补齐工具链：**SQLAlchemy**（2005，Mike Bayer）成为事实标准 ORM，2011 年配套的 **Alembic** 把「改表结构」变成可版本化的迁移脚本；而**缓存**的缺口由 **Redis**（2009，Salvatore Sanfilippo）补上——内存键值存储、单线程模型、支持过期与多种淘汰策略，成为「缓存查询结果」的标准答案。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| SQL-86 / SQL-92 | 1986-1992 | 首个 SQL 标准；SQL-92 成为所有数据库共用的语法基线 |
| MySQL / PostgreSQL | 1995-1996 | 开源关系数据库两强相继发布 |
| SQLite 1.0 | 2000 | D. Richard Hipp 发布——嵌入式零配置数据库 |
| SQLite 3.0 | 2004 | 重写存储引擎（B-tree 存储、类型亲和） |
| SQLAlchemy | 2005 | Mike Bayer 发布——Python 事实标准 ORM |
| Redis | 2009 | 内存键值存储发布——缓存事实标准 |
| SQLite 3.7 | 2010 | 引入 WAL 模式，读写并发能力大幅提升 |
| Alembic | 2011 | 数据库迁移工具发布——与 SQLAlchemy 配套 |

本文示例以 **SQLite（标准库 `sqlite3`）** 为基线（标准库零安装、SQL 语法最贴近标准，本阶段「SQL 优先」的最佳载体），SQLAlchemy 以 **2.0.43** 为基线（本机验证工具链实测版本；2.0 的 `Mapped` 类型化风格是当前生态最稳定的部分），缓存以 **redis-py 8.0.1 + redis-server 8.x** 为基线（本机已装，示例 6 用真实 server 实测）。验证工具链：Python 3.13.9 + sqlalchemy 2.0.43 + redis-py 8.0.1 + pytest 8.4.2（ruff 0.12.0 用于质量门禁）。**alembic 在本环境未安装**（`python3 -c "import alembic"` 报 ModuleNotFoundError）——迁移能力用手写 `schema_version` 等价实现（已验证，见 3.7 与示例 5），Alembic 以概念讲解呈现，装好后即由 `alembic revision --autogenerate` + `alembic upgrade head` 接管。

## 3. 语法与参数

### 3.1 SQL 基础（DDL·DML·DQL·约束·参数化）

**SQL（Structured Query Language，结构化查询语言）** 按用途分三类：**DDL**（数据定义，`CREATE`/`ALTER`/`DROP`）、**DML**（数据操作，`INSERT`/`UPDATE`/`DELETE`）、**DQL**（数据查询，`SELECT`）。建表时用**约束（Constraint）** 把规则写进数据库：`PRIMARY KEY` 主键、`UNIQUE` 唯一、`NOT NULL` 非空、`FOREIGN KEY` 外键、`DEFAULT` 默认值。

```python
# 关键片段：examples/ex01-sqlite-crud.py —— 用户 CRUD（完整版见示例 1，本机已验证）
import sqlite3
conn = sqlite3.connect("app.db")
conn.row_factory = sqlite3.Row                  # 行按列名访问——dict(row) 的前提
conn.execute("""CREATE TABLE users (                       -- DDL：建表
    id INTEGER PRIMARY KEY,                                -- 自增主键
    name TEXT NOT NULL,                                    -- 非空约束
    email TEXT UNIQUE                                      -- 唯一约束
)""")
conn.execute("INSERT INTO users (name, email) VALUES (?, ?)",  # DML：参数化占位符
             ("Alice", "alice@example.com"))
row = conn.execute("SELECT * FROM users WHERE name = ?",       # DQL：条件查询
                   ("Alice",)).fetchone()
print(dict(row))                                          # 行支持按列名访问
try:                                                      # 唯一约束冲突
    conn.execute("INSERT INTO users (name, email) VALUES (?, ?)",
                 ("Dup", "alice@example.com"))
    conn.commit()
except sqlite3.IntegrityError as e:
    conn.rollback()                                       # 冲突后事务要回滚
    print(e)                                              # UNIQUE constraint failed
```

要点：

- **参数化查询（Parameterized Query）** 是铁律：值永远用 `?` 占位传入，**绝不字符串拼接 SQL**——拼接是 SQL 注入（SQL Injection）的根源（练习 1 实测：`' OR '1'='1` 这类恶意输入命中 0 行）。
- **关联与聚合**：`JOIN` 把多张表按关联字段拼起来（`LEFT JOIN` 保留左表全量），`GROUP BY` + 聚合函数（`COUNT`/`SUM`/`AVG`）做分组统计——车辆状态按设备分组统计在线时长就是这种查询（project 的 `stats()` 与 ph09 数据分析阶段的分组统计思维同源）。
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

- **`commit()` 才落盘**：`execute` 只是把 SQL 送进事务，不提交重启即丢；`with sqlite3.connect(...) as conn:` 上下文管理器会在成功时自动提交、异常时自动回滚（但**不会关闭连接**——用完要自己 `close()`）。
- 常用读取 API：`fetchone()`/`fetchall()`/`fetchmany(n)`；写操作看 `cur.rowcount` 影响行数、`lastrowid` 新主键。
- **坑（连接跨线程）**：默认连接同一时刻只允许一个线程使用，多线程要 `check_same_thread=False` 并自行加锁（ph10 Web 后端阶段已用 `connect_args` 传过）。

### 3.3 SQLAlchemy Core 与 ORM（SQL 优先，ORM 只做映射层）

**SQL 基础比 ORM 更重要**（roadmap 必会概念）：ORM 的全部能力都是「生成 SQL」，看不懂 SQL 就调不好 ORM——`EXPLAIN` 查出来的慢查询、事务边界、索引选择，最终都要回到 SQL 层解决。SQLAlchemy 提供两层：**Core** 是「SQL 表达式 + 连接管理」（贴近 SQL），**ORM** 是「对象 ↔ 行」映射（ph10 Web 后端阶段已用 `Mapped`/`mapped_column`/`Session` 入门，本阶段强调其背后就是 SQL）。

```python
# examples/ex04-sqlalchemy.py —— Core 与 ORM（完整版见示例 4，本机已验证）
# 验证环境：Python 3.13.9，sqlalchemy 2.0.43
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
engine = create_engine("sqlite:///app.db")
with engine.connect() as conn:                          # Core：SQL 表达式
    rows = conn.execute(text("SELECT name FROM users WHERE city = :c"),
                        {"c": "Beijing"})
    print(rows.fetchall())

class Base(DeclarativeBase):                            # ORM：对象 ↔ 行映射
    pass
class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[str] = mapped_column(unique=True, index=True)
    model: Mapped[str]
    online: Mapped[bool] = mapped_column(default=False)
Base.metadata.create_all(engine)                        # 演示建表；正式项目用迁移（见 3.7）
with Session(engine) as session:                        # with 结束自动 close——防连接泄漏
    session.add(Device(vin="V001", model="EV-A"))
    session.commit()                                    # 忘记 commit = 数据没写进去
```

要点：

- **会读 ORM 生成的 SQL**：打开 echo（`create_engine(url, echo=True)`）能看到每条语句，这是排查 N+1、走没走索引的第一步（ph10 Web 后端阶段 3.7 的 N+1 坑在此闭环；示例 4 实测打印了 ORM 生成的 `INSERT`/`SELECT`）。
- Core 与 ORM 同源：ORM 查询最终也是生成 Core 表达式再编译成 SQL；连接池、事务、迁移由引擎统一管理。
- 本阶段「SQL 优先」的落法：**先会写 SQL，再用 ORM 减少样板**——示例 1/3/5 用标准库把 SQL 本身练透，示例 4 展示 ORM 背后就是 SQL；连接池参数（3.6）由引擎统一配置。

### 3.4 事务与 ACID（BEGIN·COMMIT·ROLLBACK）

**事务（Transaction）** 把一组操作包成一个原子单位：要么全部成功（`COMMIT`），要么全部不生效（`ROLLBACK`）。**事务保证一致性边界**（roadmap 必会概念）——「转账：A 扣钱 + B 加钱」必须同生共死，否则 A 扣了 B 没加就是数据不一致。

```python
# examples/ex02-transaction.py —— 转账事务（完整版见示例 2，本机已验证）
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
- `sqlite3` 默认 `isolation_level="DEFERRED"`（Python 3.12 起，此前默认 `""`，隐式事务行为一致）：`INSERT`/`UPDATE`/`DELETE` 前自动 `BEGIN`，`commit()` 才结束——**每个写操作后都要 commit**，否则数据「看似成功实则丢失」。（时效提示：legacy 事务控制仍是默认且未弃用，但官方推荐改用 `autocommit` 属性——`connect()` 的 `autocommit` 默认值未来将改为 `False`，届时 `isolation_level` 不再生效）
- 手动事务用 `isolation_level = None` + 显式 `BEGIN`（示例 2 完整演示失败回滚与 SAVEPOINT 嵌套回滚）；真实项目里这个边界通常由 ORM Session 管理（ph10 Web 后端阶段的 `session.commit()`/`session.rollback()` 就是同一件事）。

### 3.5 索引（CREATE INDEX·EXPLAIN QUERY PLAN·最左前缀）

**索引（Index）** 是数据库为加速查询建立的「目录」：没有它，`WHERE` 只能**全表扫描（Full Table Scan）**，百万行表一条查询就是百万次比较；有了索引，查询走 B+ 树按需定位（原理见 4.1）。

```python
# examples/ex03-index-query-plan.py —— 两万行实测（完整版见示例 3，本机已验证）
import sqlite3
conn = sqlite3.connect("perf.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS devices (id INTEGER PRIMARY KEY, vin TEXT, model TEXT, online INTEGER)")
cur.executemany("INSERT INTO devices (vin, model, online) VALUES (?, ?, ?)",
                [(f"VIN{i:06d}", f"EV-{i % 5}", i % 2) for i in range(20000)])
conn.commit()
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM devices WHERE vin = 'VIN000123'")
print(cur.fetchall())                    # 无索引：SCAN devices（全表扫描）
cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_vin ON devices(vin)")
cur.execute("EXPLAIN QUERY PLAN SELECT * FROM devices WHERE vin = 'VIN000123'")
print(cur.fetchall())                    # 有索引：SEARCH ... USING INDEX idx_devices_vin
```

要点：

- **`EXPLAIN QUERY PLAN` 是 SQLite 的「体检报告」**：看到 `SCAN` 就该考虑加索引，看到 `SEARCH ... USING INDEX` 说明索引生效。示例 3 实测：两万行按 vin 查询从 `SCAN`（0.34 ms）变为 `SEARCH ... USING INDEX`（0.02 ms）；练习 3 把数据量加到 10 万行，复合索引约快 21 倍（1.89 ms → 0.09 ms）。
- **UNIQUE 约束自带索引**：`vin TEXT UNIQUE` 会隐式创建 `sqlite_autoindex_*` 索引，精确查询天生走索引（练习 2 实测）；非唯一列才需要手动 `CREATE INDEX`。
- **索引不是越多越好**：每多一个索引，写入就多维护一份（写放大），小表、写多读少、频繁更新的列都不该加；索引是**空间换时间**——练习 2 实测两万行小表上耗时差异不明显（数据都在页缓存里），这正是「小表不加索引」的证据。
- **复合索引（Composite Index）按最左前缀（Leftmost Prefix）生效**：`(device_id, ts)` 索引能加速 `WHERE device_id=?` 和 `WHERE device_id=? AND ts BETWEEN ...`，但**不能**加速只按 `ts` 的查询——列顺序即前缀顺序（练习 3 实测最左前缀）。

### 3.6 连接池（Connection Pool·池参数）

**连接池（Connection Pool）** 是「连接的复用仓库」：建立数据库连接是昂贵操作（TCP 握手 + 认证 + 内存分配），每次请求新建、用完销毁太浪费；连接池维护一批连接（懒创建、按需生长到 `pool_size`），请求来了**借**、用完**还**，超出的请求排队等待（原理见 4.4）。

```python
# 依赖：pip install sqlalchemy pymysql（MySQL 场景；需 MySQL 服务，本环境未验证）
from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://user:pass@host/db",
                       pool_size=5,          # 池内常驻连接数
                       max_overflow=10,      # 高峰期最多再开 10 条
                       pool_recycle=3600,    # 连接超过 1 小时回收重建
                       pool_pre_ping=True)   # 借出前 ping 验证连接存活
```

要点：

- **池是「复用」，不是「无限开」**：`pool_size + max_overflow` 是连接上限，超过就阻塞等待——连接泄漏（借了不还）会慢慢把池占满，最终全部请求超时（ph10 Web 后端阶段的「Session 用完必须关」就是防这个）。
- **`pool_pre_ping=True` 防「失效连接」**：数据库重启、网络抖动后池里的旧连接已死，借出前 ping 一下能避免「拿到手就用不了」。
- **SQLite 的特殊性**：连接极廉价（就是打开一个文件）且文件锁语义特殊，SQLAlchemy 对**文件型 SQLite 默认用 NullPool**（不池化，每会话新连接），连接池主要服务于 MySQL/PostgreSQL 这类服务器型数据库——示例 4 用 `poolclass=QueuePool` 显式指定，实测池状态从「Connections in pool: 0」到「借出 1 条后 Checked out: 1」再到「归还后 pool: 1」。

### 3.7 迁移（schema_version 手写迁移·Alembic 入门）

**迁移（Migration）** 把「改表结构」变成**版本化的 SQL**：每个版本一段 SQL、按顺序执行、已执行版本记录在 `schema_version` 表里——结构变更可回放、可审计、可追踪。**迁移脚本让结构变更可追踪**（roadmap 必会概念）。alembic 在本环境未安装，这里用手写 `schema_version` 演示同一套思想（完整可运行版见示例 5）；装好 alembic 后，这套逻辑由 `alembic revision --autogenerate` + `alembic upgrade head` 接管（ph10 Web 后端阶段 3.7 已入门命令形态）。

```python
# examples/ex05-migration.py —— 手写迁移（完整版见示例 5，本机已验证）
MIGRATIONS = [                                  # 版本号递增，只增不改
    (1, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"),
    (2, "ALTER TABLE users ADD COLUMN email TEXT"),
    (3, "CREATE INDEX idx_users_name ON users(name)"),
    (4, "ALTER TABLE users ADD COLUMN city TEXT"),
]
# migrate() 逻辑：对每个版本，若 version <= 当前版本则跳过；否则 BEGIN → 执行 SQL →
# 记入 schema_version → COMMIT；异常 ROLLBACK 整体回滚
```

要点：

- **迁移 = 版本化的 SQL**：数据库结构从 v1 一步步升级到 v4，每个版本一条记录，可回放、可审计（谁在什么时间把结构改成了什么样）；示例 5 实测：首次应用 v1~v4、当前版本 `4`，再次执行跳过全部（幂等），失败在事务里回滚不留半成品。
- **Alembic 只是把这个框架工程化**：`upgrade head` 应用、`downgrade` 回退、`autogenerate` 对比「模型 vs 数据库」自动生成迁移——与手写 `schema_version` 是同一套思想（「未在本环境验证（alembic 未安装）」，装好后即可用）。
- **坑（手工改表对不上）**：多环境手工 `ALTER TABLE` 最容易「开发环境有、生产环境没有」——迁移脚本让每个环境执行同一份 `upgrade head`，杜绝结构漂移。

### 3.8 Redis 数据类型与命令（string·hash·list·set·zset·过期）

**Redis** 是内存键值存储（In-Memory Key-Value Store）：数据存在内存里，读写是微秒级，比查磁盘数据库快两三个数量级——典型用法是把**热点查询结果**缓存起来（查询先看缓存，命中即返回，未命中查库再回填）。核心是五种数据类型 + 过期机制：

| 类型 | 示例命令 | 用途 |
|------|---------|------|
| string | `SET`/`GET`/`SETEX` | 缓存 JSON 字符串、计数器（`INCR`） |
| hash | `HSET`/`HGETALL` | 存对象字段（设备信息） |
| list | `LPUSH`/`LRANGE` | 消息队列、最近列表 |
| set | `SADD`/`SISMEMBER` | 去重、标签集合 |
| zset | `ZADD`/`ZRANGEBYSCORE` | 排行榜、按分数排序 |

```bash
# redis-cli 命令（需 redis-server；本环境已装 redis-server 8.x，示例 6 实测）
SET device:1001 '{"vin":"V001"}' EX 300   # 5 分钟过期（TTL）
GET device:1001
EXPIRE device:1001 60                     # 动态调整过期
TTL  device:1001                          # 查剩余秒数（-1 永不过期）
```

```python
# examples/ex06-redis-cache.py —— 真实 redis-server 实测（完整版见示例 6，本机已验证）
# 验证环境：Python 3.13.9，redis-py 8.0.1 + redis-server 8.x
import redis
r = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
r.set("device:1001", '{"vin":"V001"}', ex=60)   # 写缓存 + 过期时间（redis-py 8 推荐 set 而非 setex）
data = r.get("device:1001")                     # 命中返回字符串，未命中返回 None
```

要点：

- **缓存要有过期和失效策略**（roadmap 必会概念）：`EXPIRE`/`TTL` 管**过期**（数据变旧就失效），`maxmemory-policy` 管**淘汰**（内存满时按策略腾位置，`allkeys-lru` 淘汰最久未用）；再配合**主动失效**（写库时同步删/更新缓存）——三个机制缺一不可，详见 4.5 与示例 6/练习 4。
- **pymongo/motor 可选**：MongoDB 是文档型 NoSQL（存 JSON 文档、无表结构），roadmap 仅列为了解项——本阶段不深入，先把关系型 + 缓存练透。
- 生产注意：缓存 key 要有统一命名（如 `device:{id}`），value 一般是序列化后的 JSON（配合 ph10 Web 后端阶段的 Pydantic `model_dump`）。

**缓存设计三问**（比"怎么缓存"更先回答的三个问题）：

1. **该不该缓存**：数据**读多写少**且**容忍短暂不一致**才值得（热点查询）；写多或强一致的场景别缓存——缓存是加在"读路径"上的加速，不是一致性工具；
2. **缓多久（TTL 怎么定）**：取"业务可接受的数据陈旧窗口"——变化快的取短（30 秒级），变化慢的可长（分钟/小时级）；TTL 的本质是"我允许旧多久"；
3. **怎么失效**：TTL 过期是**兜底**（到点自动失效），写库时**主动删/更新缓存**才是及时性来源（示例 6/练习 4 的 cache-aside：写库后失效对应 key）——两件事都要做，缺一个要么陈旧要么永久。

## 4. 底层原理

### 4.1 B+ 树索引（为什么索引快）

索引的数据结构是 **B+ 树（B+ Tree）**：一种多路平衡查找树，所有数据都存在**叶子节点**，内部节点只存「键 + 指针」用来路由。一棵树的节点按**页（Page）** 存储（SQLite 默认 4KB/页），每页能装几十上百个键，所以**树高很矮**——百万行数据的索引树通常只有 3-4 层：查一次索引 = 3-4 次磁盘页读取，而全表扫描 = 百万次页读取，这就是索引快几个数量级的原理。表的主键（`INTEGER PRIMARY KEY`）在 SQLite 里是**聚簇索引（Clustered Index）**：数据行直接存在主键树的叶子页上；普通索引（二级索引）的叶子只存「索引键 + 主键值」，命中后还要按主键**回表（Table Lookup）** 取整行——如果查询需要的列全在索引里，就能**覆盖索引（Covering Index）** 免回表，这是「索引里多放一列」能加速的秘密。

### 4.2 事务的 WAL 与回滚日志（SQLite 的持久化与崩溃恢复）

SQLite 用两种日志保证事务的**持久性与原子性**。默认的 **rollback journal 模式**（`journal_mode=DELETE`）写的是「回滚日志」：事务开始先把将改动的旧页副本写进日志文件，再改数据库页，全部成功后才把日志删除——崩溃时若日志还在，就用日志把数据库**还原到事务前**（回滚），保证「要么全成、要么全无」。**WAL（Write-Ahead Logging，预写日志）模式**（`PRAGMA journal_mode=WAL`，3.7.0 起）换了个思路：改动**先追加写进独立的 `-wal` 日志文件**，再在合适时机（checkpoint）合并回主库文件——这样读事务只读主库快照、写事务只追加日志，**读者不阻塞写者**，并发能力大幅提升；崩溃恢复时重放 WAL 即可。两种模式都依赖 `fsync` 把日志真正刷到磁盘——「提交成功」 = 日志已落盘，这是持久性的物理保证。

### 4.3 隔离级别（并发事务的四种边界）

**隔离性（Isolation）** 处理「多个事务同时读写同一批数据」时的干扰，标准定义了四种**隔离级别（Isolation Level）**，从松到严：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| 读未提交（Read Uncommitted） | 可能 | 可能 | 可能 |
| 读已提交（Read Committed） | 避免 | 可能 | 可能 |
| 可重复读（Repeatable Read） | 避免 | 避免 | 可能 |
| 串行化（Serializable） | 避免 | 避免 | 避免 |

**脏读（Dirty Read）** 是读到别人未提交的数据（可能被回滚）；**不可重复读（Non-Repeatable Read）** 是同一事务两次读同一行结果不同（别人改了并提交）；**幻读（Phantom Read）** 是同一事务两次范围查询多出/少了行。**SQLite 默认就是串行化**：整个数据库单写者 + 锁控制，天然没有脏读幻读（代价是写并发受限，WAL 缓解读阻塞）；**PostgreSQL 默认读已提交**（每语句快照），**MySQL InnoDB 默认可重复读**（事务快照）。工程上「事务边界」的选择就是在这张表上权衡：要强一致选串行化/可重复读，要高并发容忍一点弱隔离。

### 4.4 连接池原理（借·还·失效）

连接池本质是「**有限连接的出借队列**」（SQLAlchemy 的 `QueuePool`）：连接**懒创建**、按需生长，最多常驻 `pool_size` 条；请求来取连接（借出），用完归还（还池）；池满（全部借出）且有 `max_overflow` 余量就临时新建，**超过上限则调用方阻塞等待**（可配 `timeout` 抛超时错误）。三个工程细节：一是**连接会失效**——数据库重启、网络中断后池里「看起来活着」的连接实际已死，`pool_pre_ping` 在借出前发一个轻量探活；二是**连接要回收**——`pool_recycle` 定期重建连接，规避服务端空闲超时断开和内存累积；三是**会话（Session）≠ 连接**——SQLAlchemy 里 Session 是「工作单元」（ph10 Web 后端阶段 4.4），它按需从池里借连接、事务结束归还——所以「会话泄漏」的真相是**连接借了没还**，池被占满后所有新请求排队饿死。

### 4.5 Redis 单线程事件循环与持久化（为什么快·怎么不丢）

Redis **命令执行是单线程的**：一个进程用**事件循环（Event Loop，epoll）** 处理所有客户端连接，同一时刻只有一条命令在跑。单线程看似慢，实则快：**数据全在内存**（无磁盘 I/O）、**命令天然原子**（无锁、无上下文切换、无竞争）；代价是**单条命令必须快**——`KEYS *`、大键遍历这类 O(N) 命令会阻塞整个服务，生产禁用。持久化两条路：**RDB**（定时把内存快照 fork 子进程写盘，恢复快、可能丢最近一次快照后的数据）与 **AOF**（把每条写命令追加到日志，`appendfsync` 策略控制刷盘频率，最多丢 1 秒数据）；两者可同时开启。**过期与淘汰**：Redis 对带 TTL 的键用「**惰性删除**（访问时发现过期即删）+ **定期删除**（周期抽样清理）」双策略；内存达到 `maxmemory` 后按 `maxmemory-policy` 淘汰，`allkeys-lru` 是最常用的「近似 LRU」。缓存的三大坑由此展开：**穿透**（查不存在的 key 每次都打库——对策：空值也缓存 + 布隆过滤器）、**击穿**（热点 key 过期瞬间打爆库——对策：互斥锁重建）、**雪崩**（大量 key 同时过期——对策：随机 TTL + 多级缓存）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 用户 CRUD | sqlite3 建表 + 增删改查 + 参数化查询 + 唯一约束 |
| 设备信息管理 | vin 唯一约束（自带索引）+ 普通索引 + 迁移脚本加字段（如 `online` 状态） |
| 车辆状态表 | 高频写入 + 按设备/时间查询 + 复合索引（`(device_id, ts)`） |
| 热点查询缓存 | Redis string 缓存查询结果 + TTL 过期 + 写库主动失效 |
| 事务型业务（订单/转账） | BEGIN/COMMIT/ROLLBACK + 一致性边界 + 失败回滚 |
| 数据平台后端 | SQLAlchemy + Alembic 迁移 + 连接池 + Redis 缓存（承接 ph10 Web 后端阶段） |

**不适合此阶段的事项**：

- 大规模异步与消息（Kafka、MQ、百万级并发连接）：[ph14 并发、并行与异步阶段](../ph14-concurrency-async/14-concurrency-async.md)（roadmap 第 14 节）
- 生产部署（Nginx、Docker、K8s、CI/CD、监控告警）：[ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）
- NoSQL 文档模型深入（MongoDB 聚合、分片）：本阶段 pymongo/motor 仅可选了解
- 分布式事务、分库分表、读写分离：单库起步的业务系统先不涉及，ph16 部署与 DevOps 阶段再谈

**SQL vs NoSQL（什么时候别用 SQL 关系型）**：本阶段以关系型为底，是因为绝大多数业务数据**有结构、有关系、要事务**。但当数据形态变了，关系型就不是最优解：**文档型（MongoDB）** 适合「结构多变、以整文档读写为主」的 JSON 数据（埋点、配置、半结构化日志）；**键值型（Redis）** 适合「按 key 高速读写、要过期」的缓存与会话；**宽表/列存** 适合海量分析型查询。判据一句话：**数据有固定关系且要事务 → SQL；数据是自包含文档、结构会变 → 文档库；只要"快取一个值" → Redis**。本阶段先把关系型练透——迁移到 NoSQL 时，反而常常发现业务其实没那么需要 NoSQL。

**新表设计前的自查清单**：

- 主键选对了吗？——绝大多数场景用自增 `INTEGER PRIMARY KEY`（代理键）；业务唯一标识（`vin`/`email`）用 `UNIQUE` 约束表达，不要拿它当主键（会随业务变化）
- 约束进表了吗？——`NOT NULL`/`UNIQUE`/`DEFAULT`/`FOREIGN KEY` 让数据库把关，而不是靠应用层每次检查
- 索引是按查询设计的吗？——先写清楚要跑的查询，再定索引并用 `EXPLAIN QUERY PLAN` 验证（3.5）；别建了表顺手把每列都加索引
- 规范化到够用为止——按业务实体分表、避免重复存储，但别为"理论第三范式"把一张表拆成五张（查询要 JOIN 五次就是过度设计）

**SQL 反模式自查表**：

| 反模式 | 症状 | 修法 |
|--------|------|------|
| `SELECT *` | 拉回不需要的列，网络与内存浪费 | 只列需要的字段 |
| `WHERE` 里包函数 | `WHERE YEAR(ts)=2026` 索引失效（每行都要算函数） | 改成区间 `ts >= '2026-01-01' AND ts < '2027-01-01'` |
| `LIKE '%xx%'` | 前缀通配无法走普通索引 | 前缀固定用 `LIKE 'xx%'`；全文需求上全文索引（超出本阶段） |
| `UPDATE`/`DELETE` 忘 `WHERE` | 全表被改/被删 | 写操作前先用 `SELECT` 验证条件命中行数（3.1） |
| 循环里逐行查库（N+1） | 100 行循环 = 101 次查询 | 一次 `JOIN`/`IN` 取回（ph10 Web 后端阶段已实测 N+1 坑） |
| 顺手给所有列加索引 | 写入变慢（每索引一份维护） | 只为真实查询的列加索引，`EXPLAIN` 验证（3.5） |

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条运行。全部示例**离线可跑、本机已验证**（Python 3.13.9），数据库文件（`.db`）与 redis 数据目录一律写到**系统临时目录**、脚本结束自动回收——运行后用 `git status` 可确认工作区干净；唯一例外是示例 6 在脚本内起一个临时 `redis-server` 子进程（随机端口、`--save ''` 不持久化），结束时 `terminate()` 干净关闭。依赖状态：sqlite3 标准库（零安装）、sqlalchemy 2.0.43、redis-py 8.0.1 + redis-server 8.x 均已安装并实测；alembic **未安装**——示例 5 用手写 `schema_version` 等价实现（见 3.7）。

### 示例 1：用户 CRUD（标准库 sqlite3，对应 roadmap 示例）

呼应 3.1/3.2：建表 + 增删改查 + 参数化查询 + 唯一约束冲突处理，`create_user`/`get_user`/`update_user`/`delete_user` 四函数即完整 CRUD 服务。完整文件 `examples/ex01-sqlite-crud.py`。

```python
# examples/ex01-sqlite-crud.py —— 用户 CRUD：标准库 sqlite3（离线可跑，已验证）
def create_user(conn, name, email):          # 返回新行主键
    return conn.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
    ).lastrowid
```

实测输出：`create_user -> id: 1`；批量插入后总行数 `3`；重复 email 抛 `UNIQUE constraint failed: users.email`（捕获后 `rollback()`）；`update_user` rowcount `1`；`delete_user` rowcount `1`、剩余 `2`。

### 示例 2：事务与失败回滚（转账 + SAVEPOINT）

呼应 3.4/4.2：手动事务 `isolation_level = None` + 显式 `BEGIN`，演示「事务保证一致性边界」与 SAVEPOINT 嵌套回滚。完整文件 `examples/ex02-transaction.py`。

```python
# examples/ex02-transaction.py —— 转账事务（离线可跑，已验证）
def transfer(cur, frm, to, amount):
    cur.execute("BEGIN")
    try:
        bal = cur.execute("SELECT balance FROM accounts WHERE name = ?", (frm,)).fetchone()[0]
        if bal < amount:
            raise ValueError(f"{frm} 余额不足: {bal}")
        cur.execute("UPDATE accounts SET balance = balance - ? WHERE name = ?", (amount, frm))
        cur.execute("UPDATE accounts SET balance = balance + ? WHERE name = ?", (amount, to))
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")              # 任一步失败 → 全部撤销
        raise
```

实测输出：初始 `[('A', 1000.0), ('B', 0.0)]`；转账 2000 失败回滚后余额不变；转账 300 成功后 `[('A', 700.0), ('B', 300.0)]`；SAVEPOINT 回滚只撤销 savepoint 之后的操作。

### 示例 3：索引与查询优化（EXPLAIN QUERY PLAN + 实测耗时）

呼应 3.5/4.1：两万行数据按 vin 精确查询，先看全表扫描的执行计划与耗时，加索引后再对比。完整文件 `examples/ex03-index-query-plan.py`。

```python
# examples/ex03-index-query-plan.py —— 两万行实测（离线可跑，已验证）
plan, ms = measure(cur, "VIN000123")         # 无索引
print(plan, f"{ms:.2f} ms")                  # SCAN devices  0.34 ms
cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_vin ON devices(vin)")
plan, ms = measure(cur, "VIN000123")         # 有索引
print(plan, f"{ms:.2f} ms")                  # SEARCH ... USING INDEX idx_devices_vin  0.02 ms
```

实测输出：执行计划从 `SCAN devices` 变为 `SEARCH devices USING INDEX idx_devices_vin (vin=?)`，耗时从 `0.34 ms` 降到 `0.02 ms`（约 17 倍）；数据量再大一个数量级时差距更明显（练习 3 在 10 万行上约 21 倍）。**判断「要不要索引」先跑 `EXPLAIN QUERY PLAN`**——这是「SQL 基础比 ORM 更重要」在性能上的落点。

### 示例 4：SQLAlchemy 2.0 Core 与 ORM（echo 看 SQL + 连接池状态）

呼应 3.3/3.6：Core `text()` 查询、ORM `Mapped` 模型 + Session、`echo=True` 打印生成的 SQL、显式 `QueuePool` 看池状态。完整文件 `examples/ex04-sqlalchemy.py`。

```python
# examples/ex04-sqlalchemy.py —— SQLAlchemy 2.0（离线可跑，已验证，sqlalchemy 2.0.43）
engine = create_engine(URL, echo=True)       # echo=True：打印每条 ORM 生成的 SQL
Base.metadata.create_all(engine)
with Session(engine) as session:
    session.add(Device(vin="V001", model="EV-A"))
    session.commit()
    device = session.scalars(select(Device).where(Device.vin == "V001")).one()
```

实测输出：`echo` 打印了 ORM 生成的 `CREATE TABLE devices`、`CREATE UNIQUE INDEX ix_devices_vin`、`INSERT INTO devices` 与 `SELECT devices.id, devices.vin, ...`——「ORM 只是生成 SQL 的映射层」直接可见；连接池部分 `QueuePool(pool_size=2, max_overflow=1)` 实测池状态从「Connections in pool: 0」→「借出 1 条后 Checked out: 1」→「归还后 pool: 1」。

### 示例 5：迁移脚本（schema_version 手写迁移，幂等 + 失败回滚）

呼应 3.7：alembic 未安装，用手写 `schema_version` 演示同一套迁移思想——每个版本一段 SQL、事务内执行、失败回滚、可重放。完整文件 `examples/ex05-migration.py`。

```python
# examples/ex05-migration.py —— 手写迁移（离线可跑，已验证）
MIGRATIONS = [
    (1, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"),
    (2, "ALTER TABLE users ADD COLUMN email TEXT"),
    (3, "CREATE INDEX idx_users_name ON users(name)"),
    (4, "ALTER TABLE users ADD COLUMN city TEXT"),
]
```

实测输出：首次应用 v1~v4、当前版本 `4`；再次执行跳过全部（幂等，版本仍为 `4`）；插入含 v2/v4 列的数据成功——结构变更可追踪、可重放。装好 alembic 后由 `alembic revision --autogenerate` + `alembic upgrade head` 接管（ph10 Web 后端阶段 3.7，未在本环境验证）。

### 示例 6：Redis 缓存（真实 redis-server：string/TTL/EXPIRE + 缓存旁路耗时）

呼应 3.8/4.5：脚本内起临时 `redis-server` 子进程（随机端口、临时目录），演示 string 读写 + TTL/EXPIRE + 缓存旁路（cache-aside）的命中/未命中耗时，结束 `terminate()` 干净关闭。完整文件 `examples/ex06-redis-cache.py`。

```python
# examples/ex06-redis-cache.py —— 真实 redis-server 实测（离线可跑，已验证）
def get_device(r, device_id):                # 缓存旁路：先查缓存，未命中查库回填
    key = f"device:{device_id}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached), "hit"
    data = slow_query(device_id)             # 模拟 0.3s 慢查询
    r.set(key, json.dumps(data), ex=TTL)     # 写缓存 + 过期时间
    return data, "miss"
```

实测输出：`SET + GET` 返回 JSON、TTL `60` 秒、`EXPIRE` 调为 `120`；缓存旁路——首次 `miss 302 ms` → 第二次 `hit 0.1 ms`（快约 3000 倍量级）→ TTL 过期后重新 `miss 305 ms`；脚本结束打印「redis-server 已关闭，临时目录已回收」。

## 7. 总结

### 关键要点

1. **SQL 基础比 ORM 更重要**：ORM 只是生成 SQL 的映射层，`EXPLAIN QUERY PLAN`、事务边界、索引选择最终都在 SQL 层解决（roadmap 必会概念）
2. **迁移脚本让结构变更可追踪**：结构变更 = 版本化的 SQL，事务内执行、失败回滚、可重放——手写 `schema_version` 与 Alembic 是同一套思想（roadmap 必会概念）
3. **事务保证一致性边界**：`BEGIN`/`COMMIT`/`ROLLBACK` 让一组操作同生共死，失败必须回滚，否则半提交就是数据不一致（roadmap 必会概念）
4. **缓存要有过期和失效策略**：TTL 过期 + LRU 淘汰 + 主动失效三者缺一不可，穿透/击穿/雪崩各有对策（roadmap 必会概念）
5. **参数化查询是铁律**：值永远走占位符，绝不拼接 SQL——SQL 注入的防线在第一行代码（练习 1 实测注入命中 0 行）
6. **`commit()` 才落盘**：忘 commit = 数据丢失；`IntegrityError` 后要 `rollback()`，否则坏事务污染后续操作
7. **索引是空间换时间**：`EXPLAIN QUERY PLAN` 看 `SCAN` 还是 `SEARCH`（示例 3 实测 0.34 ms → 0.02 ms）；UNIQUE 自带索引；复合索引最左前缀生效；小表不加索引
8. **连接池是「借还」不是「无限开」**：`pool_size`/`max_overflow`/`pool_recycle`/`pool_pre_ping`；会话泄漏 = 连接借了没还
9. **SQLite 串行化、MySQL/PostgreSQL 各有默认隔离级别**：隔离级别是并发与一致性的权衡表
10. **Redis 单线程也快**：内存 + 事件循环 + 命令原子；RDB/AOF 管持久化，`EXPIRE`/`maxmemory-policy` 管缓存生命周期
11. **选型看数据形态**：有固定关系且要事务 → SQL；自包含 JSON 文档 → 文档库；只要快取一个值 → Redis——先把关系型练透，迁移到 NoSQL 时反而更清楚"到底需不需要它"（5 章判据）
12. **设计表先想查询、写 SQL 先查反模式**：主键/约束/索引按真实查询设计并用 `EXPLAIN` 验证；`SELECT *`、函数包列、忘 WHERE、N+1、乱加索引都在 5 章自查表里

### 阶段验收清单

- [ ] 能建表和 CRUD：`sqlite3` 建表 + 增删改查 + 参数化查询 + 唯一约束（对应 roadmap「能建表和 CRUD」）
- [ ] 能写迁移脚本：手写 `schema_version` 迁移，结构变更可版本化、可重放、失败回滚（对应 roadmap「能写迁移脚本」）
- [ ] 能设计基础缓存：TTL 过期 + LRU 淘汰 + 主动失效，能解释穿透/击穿/雪崩（对应 roadmap「能设计基础缓存」）
- [ ] 能说清四个必会概念：SQL 优先、迁移可追踪、事务一致性边界、缓存过期失效
- [ ] 能按"缓存设计三问"决定该不该缓存、TTL 多长、如何失效（3.8）；能按新表设计清单与 SQL 反模式表自检（5 章）
- [ ] 能用 `EXPLAIN QUERY PLAN` 判断是否走索引，能解释 B+ 树、WAL/回滚日志、隔离级别、连接池借还原理
- [ ] 能对照实测数字解释索引收益：两万行 0.34 ms → 0.02 ms、十万行复合索引约快 21 倍、缓存 hit 0.1 ms vs miss 305 ms

### 跨语言对比：数据库访问与缓存

| 维度 | Python | Java | Go | C++ |
|------|--------|------|----|-----|
| 驱动/标准库 | `sqlite3`（标准库）、psycopg2、PyMySQL | JDBC（`java.sql`） | `database/sql` + 驱动 | sqlite3（C 库）、libpq、mysql-connector-c++ |
| ORM | SQLAlchemy（Core+ORM） | Hibernate/JPA、MyBatis | GORM、ent、sqlx | ODB、自研封装 |
| 迁移工具 | Alembic | Flyway、Liquibase | golang-migrate、goose | 手工脚本为主 |
| 连接池 | SQLAlchemy QueuePool | HikariCP | `database/sql` 内置 | 自研/libpq 池 |
| 缓存客户端 | redis-py | Jedis、Lettuce、Spring Data Redis | go-redis | hiredis、redis-plus-plus |
| 生态特点 | SQLAlchemy 一家独大，标准库直接可用 | 企业规范（JPA）与 MyBatis 并存 | 标准库薄封装、手写 SQL 常见 | 无统一标准，多自研 |

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。与 roadmap「练习」小节一一对应，完成 4 题后继续：

- 用户 CRUD（★）：四函数 + 参数化查询防注入 + 唯一约束（提示：每个写操作后 `commit()`；重复 email 捕获 `IntegrityError` 后 `rollback()`）
- 设备信息管理（★★）：vin 唯一约束（自带索引）+ 非唯一列建索引，`EXPLAIN QUERY PLAN` 验证（提示：UNIQUE 自动建 `sqlite_autoindex_*`；小表耗时差异不明显是正常现象）
- 车辆状态表（★★）：`executemany` 批量写入 10 万行 + 复合索引 `(device_id, ts)` + 最左前缀（提示：对比有/无索引耗时，本机实测约快 21 倍）
- Redis 缓存查询结果（★★★）：缓存旁路 + TTL 过期 + 写库主动失效（提示：真实 redis-server 起在随机端口 + 临时目录，结束 `terminate()`；用 `set(key, value, ex=...)`）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**设备管理后端**——`devices` 表（vin 唯一索引）+ `device_status` 状态表（复合索引）+ 用户 CRUD + 手写迁移脚本演进结构 + 缓存设备热点查询（TTL 过期 + 写库主动失效）（对应 roadmap「推荐项目」第一个「设备管理后端」；示例 1/3/5 的合体，也是 ph10 设备管理 API 的数据层升级）。建议完成练习后再动手；roadmap 的另一个「车辆状态存储服务」可作为进阶扩展目标。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[自动化脚本阶段](../ph12-automation/12-automation.md) — 文件批处理、Excel 自动化、日志分析、接口测试、报表生成、爬虫与定时任务、paramiko/fabric 远程操作；ph11 的数据库与缓存能力让脚本能安全地读写数据、批量入库、从库取数生成报表，爬虫抓取的数据也有了落库与去重的去处。
