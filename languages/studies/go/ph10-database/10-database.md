# Go 数据库阶段

> 面向后端服务、云原生和通用数据平台方向，本阶段掌握 Go 操作数据库与缓存——SQL、database/sql、事务、连接池、索引、ORM 选型与 Redis，把"内存数据"升级为"可持久化、可并发、可上生产的存储"。

## 1. 概述

Go 数据库阶段的目标是：**能用 Go 操作数据库和缓存**——掌握 SQL 基础（CRUD/事务/索引）、database/sql 的连接池/事务/预处理机制、sqlx 与 GORM 的选型、Redis 与 go-redis 的旁路缓存，并具备配置连接池、编写事务、并发访问数据库、优化慢查询的能力。ph09 的接口全部把数据存在内存 map 里，本阶段把它们换成真实数据库：用户登录后落库、设备状态持久化、热点数据进缓存；ph11 把单体服务拆成微服务后，本阶段学到的数据层能力将下沉为各服务的独立存储。

| 核心维度 | 覆盖内容 |
|----------|---------|
| SQL 基础 | CRUD、WHERE、JOIN、索引概念（以 SQLite 可运行示例为主，点出 MySQL/PostgreSQL 方言差异） |
| database/sql | sql.Open、Query/QueryRow/Exec、Scan、Rows 遍历、sql.ErrNoRows、RowsAffected |
| 参数化查询 | 占位符 `?`/`$1`、SQL 注入防御 |
| 预处理语句 | db.Prepare、批量插入、与循环 Exec 的性能对照 |
| 连接池 | SetMaxOpenConns、SetMaxIdleConns、SetConnMaxLifetime、db.Stats() 观测 |
| 事务 | Begin/Commit/Rollback、defer 回滚兜底、事务边界由业务定义、并发防超扣 |
| 并发访问数据库 | goroutine 并发读写、busy_timeout、WAL 模式、go test -race |
| sqlx 与 ORM | sqlx 结构体扫描、gorm/ent/bun 对比与选型 |
| Redis 与缓存 | go-redis、String/Hash/Set、TTL 过期、旁路缓存、空值缓存防穿透 |
| 工程化 | 迁移（golang-migrate/goose）、慢查询、EXPLAIN 与索引调优 |

本阶段的核心信念是"**先理解 database/sql，再选择 ORM**"（必会概念）：database/sql 是标准库底座，连接池、事务、参数化、预处理的原理都在这里，sqlx/gorm 只是语法糖；**事务边界要由业务定义**——一个业务操作（如"下单减库存"）跨几条 SQL，就要包进同一个事务；**SQL 注入必须通过参数化避免**——动态值一律走占位符，绝不拼接 SQL 字符串；**连接是惰性建立的、用完必须归还**——`sql.Open` 不建连接、`Rows/Stmt/Tx` 用完即关，否则连接池被耗尽。

这个阶段只涉及单体服务 + 单数据库 + 单缓存的数据库编程（承接 ph09 Web 后端的接口，把内存 map 换成真实存储），**不涉及微服务与 RPC（gRPC、服务发现属 ph11 微服务与 RPC 阶段）、云原生部署（容器与 Kubernetes 属 ph12 云原生与部署阶段）、分布式事务与强一致（两阶段提交、Saga 属后续阶段，roadmap 未单列）、消息队列与异步解耦（Kafka/MQTT 属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)）** — 本阶段是"单体服务 + 单库 + 单缓存"。

## 2. 来源与演变

**database/sql 的"driver 分离"设计**：2012 年 database/sql 随 Go 1.0 进入标准库，效仿 net/http 的思路——标准库只定义统一 API 与 `database/sql/driver` 接口，具体数据库（MySQL、PostgreSQL、SQLite）由社区驱动实现。上层代码与数据库解耦：同一份代码换驱动即可切换数据库；这也是"先理解 database/sql"的缘由——它是所有访问方式的地基，连接池、事务、参数化、预处理都由它统一提供。**驱动必须第三方引入**：`import _ "modernc.org/sqlite"`（SQLite，纯 Go 无 cgo）、`_ "github.com/go-sql-driver/mysql"`（MySQL）、`_ "github.com/jackc/pgx/v5/stdlib"`（PostgreSQL）——标准库只有接口，没有驱动。

**SQLite 的定位**：SQLite 2000 年发布，是"嵌入式数据库"的经典——单文件、零配置、进程内，成为移动端、桌面与测试环境的事实标准；其 SQL 方言与 MySQL/PostgreSQL 大同小异（占位符同为 `?`），本阶段用它做可运行验证（纯 Go 驱动无需 cgo），生产主选仍是 MySQL/PostgreSQL。

**ORM 生态的演进**：2013 年 **gorm** 出现（最流行的全功能 ORM，链式 API + 自动迁移）；2014 年 **sqlx** 出现（轻量增强，把 Rows.Scan 样板代码压缩成 `StructScan`）；2019 年 Facebook 开源 **ent**（图状 schema 定义 + 代码生成，类型安全）；2020 年 **bun** 出现（SQL 优先，支持 raw SQL 与 query builder）。选型路线：**database/sql 学原理 → sqlx 提效率 → 复杂模型用 gorm/ent**。

**Redis 与迁移工具**：Redis 2009 年发布，以"**单线程 + 内存数据结构 + 持久化**"成为缓存、锁与热点数据的标配；Go 客户端从 **redigo**（2012）演进到 **go-redis**（github.com/redis/go-redis，2021 年迁移组织名，v9 于 2023 年发布成为主流），支持连接池、pipeline、pub/sub 与分布式锁。**迁移工具 golang-migrate（2017）与 goose（2013）** 把 schema 变更版本化：迁移文件进 git、CI 自动执行，是"数据库即代码"的基础。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| SQLite 1.0 | 2000 | 嵌入式单文件数据库发布 |
| Redis 发布 | 2009 | 单线程内存数据存储 |
| database/sql | 2012 | 随 Go 1.0 进入标准库（driver 分离设计） |
| redigo | 2012 | Go 早期 Redis 客户端 |
| gorm | 2013 | 全功能 ORM 发布；goose 迁移工具出现 |
| sqlx | 2014 | 结构体扫描简化（StructScan） |
| golang-migrate | 2017 | 版本化迁移工具 |
| ent | 2019 | Facebook 开源（代码生成 ORM） |
| bun | 2020 | SQL 优先 ORM |
| go-redis 组织迁移 | 2021 | 仓库迁至 github.com/redis/go-redis |
| go-redis v9 | 2023 | v9 发布、成为主流版本 |
| modernc.org/sqlite | 2021~ | 纯 Go 无 cgo 的 SQLite 驱动（本阶段示例基线） |

本文示例以 **modernc.org/sqlite v1.57.0** 为基线（本环境网络经 `GOPROXY=https://goproxy.cn` 拉取依赖并实际跑通——SQLite 纯 Go 驱动无需 cgo，可完整验证 database/sql 的连接池、事务、预处理行为；MySQL/PostgreSQL 生产驱动需独立服务器，本环境未启动，方言差异在文中点出），验证工具链 go1.25.6（darwin/arm64）。database/sql 的 API 自 Go 1.0 至今保持向后兼容，是本阶段最稳定的部分——把标准库原理学透后，换驱动只是改一行 import。

## 3. 语法与参数

### 3.1 SQL 基础回顾（CRUD·WHERE·JOIN·索引概念）

```sql
-- SQLite 方言（完整可运行版见 examples/ex01-sql-crud/main.go）
CREATE TABLE users (
  id         INTEGER PRIMARY KEY,          -- 自增主键（MySQL 是 AUTO_INCREMENT）
  username   TEXT NOT NULL UNIQUE,         -- 唯一约束：重复插入报错
  password   TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
SELECT id, username FROM users WHERE id = 1;                  -- 读
INSERT INTO users (username, password) VALUES ('alice', 'x'); -- 增
UPDATE users SET password = 'y' WHERE id = 1;                 -- 改
DELETE FROM users WHERE id = 1;                               -- 删
SELECT u.username, d.speed FROM users u
  JOIN devices d ON d.user_id = u.id WHERE u.id = 2;          -- 关联
CREATE INDEX idx_users_username ON users(username);           -- 索引
```

要点：SQL 是声明式语言——**说"要什么"、不说"怎么做"**；`WHERE` 过滤、`JOIN` 关联、`ORDER BY/LIMIT` 排序分页；**索引是"书的目录"**——`WHERE`/`JOIN`/`ORDER BY` 命中的列建索引，但不是越多越好（占磁盘、拖慢写入）。**方言差异**：SQLite/MySQL 占位符都是 `?`、PostgreSQL 是 `$1`；自增列 SQLite 用 `INTEGER PRIMARY KEY`、MySQL 用 `AUTO_INCREMENT`、PostgreSQL 用 `SERIAL`；upsert 写法 SQLite 是 `ON CONFLICT(col) DO UPDATE`、MySQL 是 `ON DUPLICATE KEY UPDATE`——本阶段可运行示例以 SQLite 为主、点出差异。

### 3.2 database/sql 核心（sql.Open·Query·QueryRow·Exec·Scan）

```go
// 完整可运行版见 examples/ex01-sql-crud/main.go
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0（已验证）
package main

import (
	"database/sql"
	"fmt"
	"log"

	_ "modernc.org/sqlite" // 驱动注册到 database/sql（必须第三方引入）
)

func main() {
	db, err := sql.Open("sqlite", ":memory:") // ① Open 只校验 DSN 格式，不建立连接！
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil { // ② Ping 才真正连库
		log.Fatal(err)
	}
	// ③ QueryRow 单行 + Scan；Query 多行 + Rows 循环；Exec 增删改
	var id int64
	var username, password string
	err = db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", 1).
		Scan(&id, &username, &password)
	if err == sql.ErrNoRows {
		fmt.Println("记录不存在")
	} else if err != nil {
		log.Fatal(err)
	} else {
		fmt.Printf("%d %s %s\n", id, username, password)
	}
}
```

要点：**`sql.Open` 不建连接、`db.Ping()` 才真正连库**——连接是惰性建立的；三个核心方法——**QueryRow 单行 + Scan、Query 多行 + Rows 循环、Exec 增删改**；`Scan` 按列顺序把值拷进指针。**坑：QueryRow 的 err 必须检查**——查无记录返回 `sql.ErrNoRows`，不检查就静默吞掉（唯一正确的"不存在"判定是 `errors.Is(err, sql.ErrNoRows)`）；**坑：Query 返回的 Rows 用完必须 Close**（`defer rows.Close()`），否则连接借了不还、连接池被耗尽（原理见 4.1）；**坑：UPDATE/DELETE 用 `RowsAffected()==0` 判定"未命中"**——更新不存在的 id 不会报错，只影响 0 行。

### 3.3 参数化查询与 SQL 注入防御

```go
// 完整可运行版见 examples/ex01-sql-crud/main.go
// 危险写法（反面教材）：username := "alice' OR '1'='1"
// row := db.QueryRow("SELECT * FROM users WHERE username = '" + username + "'")
username := "alice' OR '1'='1" // 恶意输入，参数化后只是普通字符串
var id int64
err = db.QueryRow("SELECT id FROM users WHERE username = ?", username).Scan(&id) // ? 占位符（PG 用 $1）
if err != nil && err != sql.ErrNoRows {
	log.Fatal(err)
}
```

要点：**参数化查询 = 占位符 + 参数分离提交**——驱动把参数作为"值"传给数据库，恶意内容永远是数据、进不了 SQL 语法层（原理见 4.3）；占位符 MySQL/SQLite 用 `?`、PostgreSQL 用 `$1/$2`。**坑：一切拼接 SQL 字符串的行为都是注入入口**——包括表名、列名、排序字段（这些不能参数化，必须白名单校验）；**坑：以为"只有用户输入才危险"**——内部拼接同样危险，规范是"所有动态值一律参数化"。

### 3.4 预处理语句（Prepare·批量插入）

```go
// 完整可运行版见 examples/ex02-connpool/main.go 的 insertPrepared
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0（已验证）
stmt, err := db.Prepare("INSERT INTO items (name) VALUES (?)") // ① 预编译：SQL 只解析编译一次
if err != nil {
	return err
}
defer stmt.Close() // ② 用完必须关，否则占用连接
for _, n := range names {
	if _, err := stmt.Exec(n); err != nil { // ③ 循环里只传参数
		return err
	}
}
```

要点：**预处理把"SQL 解析编译"与"参数绑定"分离**——同一 SQL 重复执行时只传值，省去每次的解析开销（原理见 4.3）；**循环批量插入用 Prepare、单次查询用 `QueryRow("...?", args)` 的隐式 prepare**（驱动自动处理）。**坑：stmt 忘记 Close**——预处理语句同样占用连接，用完即关；**坑：Prepare 的结果不能跨数据库实例复用**——换个 db 就要重新 Prepare。

### 3.5 连接池配置（SetMaxOpenConns 等）

```go
// 完整可运行版见 examples/ex02-connpool/main.go 的 newPooledDB
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0（已验证）
db, err := sql.Open("sqlite", "file:app.db?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
if err != nil {
	return nil, err
}
db.SetMaxOpenConns(50)                  // 最大打开连接数（含使用中）——并发上限
db.SetMaxIdleConns(25)                  // 最大空闲连接数（常驻待命）
db.SetConnMaxLifetime(30 * time.Minute) // 单条连接最长存活（防"连接老化"）
db.SetConnMaxIdleTime(5 * time.Minute)  // 空闲超时即回收
stats := db.Stats()                     // 运行期观测：OpenConnections/InUse/Idle/WaitCount...
```

要点：**database/sql 自带连接池**，四个 Set 方法就是全部配置，`db.Stats()` 可观测连接状态；**SetMaxOpenConns 是并发上限**——超过后请求排队，防数据库被打爆；**SetConnMaxLifetime 防"连接老化"**——MySQL 的 wait_timeout 会断空闲连接，定期换新连接规避"连接已死"报错；SQLite 的并发写还要在 DSN 里开 **busy_timeout**（写锁被占时等待而非立即报 `database is locked`）与 **WAL 模式**（读不阻塞写）。**坑：连接池耗尽**——handler 里忘 `rows.Close()`、事务不结束，连接只借不还，达到 MaxOpenConns 后所有请求卡死（ex02 有 Stats 观测用例）；**坑：OpenConns 设太小**（如 2）高并发吞吐骤降——按 `QPS × 单查询耗时` 估算。

### 3.6 事务（Begin·Commit·Rollback·Tx 边界）

```go
// 完整可运行版见 examples/ex03-transaction/main.go 的 Transfer
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0（已验证）
func Transfer(db *sql.DB, from, to string, amount int64) error {
	if amount <= 0 {
		return fmt.Errorf("转账金额必须为正: %d", amount) // 事务外的前置校验
	}
	tx, err := db.Begin() // ① 开启事务
	if err != nil {
		return err
	}
	defer tx.Rollback() // ② 兜底：Commit 前任何 return 都自动回滚，防"悬挂事务"
	// ③ 条件扣款：只有 balance >= amount 才扣（SQLite 无 FOR UPDATE，条件更新跨库通用）
	res, err := tx.Exec("UPDATE accounts SET balance = balance - ? WHERE username = ? AND balance >= ?",
		amount, from, amount)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return fmt.Errorf("余额不足: %s", from)
	}
	if _, err := tx.Exec("UPDATE accounts SET balance = balance + ? WHERE username = ?", amount, to); err != nil {
		return err
	}
	return tx.Commit() // ④ 全部成功才提交
}
```

要点：**事务边界由业务定义**（必会概念）——"转账"跨"扣款 + 加款"两条 SQL，必须包进同一个事务：全部成功 Commit、任一步失败 Rollback；**`defer tx.Rollback()` 是防泄漏标配**——Commit 成功后它是空操作，但中间任何 return 都保证回滚。**坑：只 Commit 不处理错误 / 忘记 Rollback**——留下"悬挂事务"占用连接与行锁；**坑：禁止裸写 `db.Exec("BEGIN")`**——database/sql 的连接池不知道你在裸开事务，可能把处于事务中的连接还回池子被其他请求复用，事务中的连接在并发下会相互踩踏导致死锁（ex03 注释有说明）；**防超扣方案对比**：MySQL 用 `SELECT ... FOR UPDATE` 行级悲观锁（ex03 注释点出），SQLite 不支持 FOR UPDATE，改用**条件更新** `UPDATE ... SET balance = balance - ? WHERE balance >= ?`——条件在 SQL 里原子判断，并发下也不会超扣（ex03 的并发用例实测 10 goroutine 转 1000 余额零超扣）。

### 3.7 并发访问数据库（goroutine·busy_timeout·WAL·race）

```go
// 完整可运行版见 examples/ex05-concurrent/main.go
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0（已验证，-race 干净）
db, err := sql.Open("sqlite",
	"file:app.db?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
if err != nil {
	return nil, err
}
db.SetMaxOpenConns(8) // 并发上限：超过的请求排队
// 20 个写 goroutine + 2 个读 goroutine 同时跑，结果一条不丢（见 runConcurrent）
```

要点：**database/sql 是并发安全的**——`*sql.DB` 可被多个 goroutine 共享，连接池负责连接分配与排队，业务代码无需加锁；但**单条连接上的操作不是并发安全的**（同一 `*sql.Tx` / `*sql.Stmt` / `*sql.Rows` 不能跨 goroutine 并发用）。SQLite 特殊点：**同一时刻只允许一个写者**——多写并发靠 busy_timeout 排队 + WAL 让读不阻塞写（ex05 实测 20 goroutine × 10 条 = 200 条一条不丢，`go test -race` 干净）；MySQL/PostgreSQL 则是多写者架构，瓶颈更多在连接数与锁竞争。**坑：以为"数据库操作要自己加锁"**——那是把连接池的活抢来干，正确做法是共享 `*sql.DB`、控制 MaxOpenConns；**坑：长事务 + 高并发**——事务独占一条连接，事务里做慢查询会一直占住连接（见 4.1）。

### 3.8 sqlx 增强与 ORM 选型（gorm/ent/bun）

```go
// 完整可运行版见 examples/ex04-sqlx-gorm/main.go
// 验证环境：go1.25.6 + sqlx v1.4.0 / gorm v1.31.2（已验证，纯 Go 驱动）
type UserRow struct {
	ID       int64  `db:"id"` // sqlx：db tag 驱动列映射
	Username string `db:"username"`
	Password string `db:"password"`
}
var users []UserRow
if err := db.Select(&users, "SELECT id, username, password FROM users ORDER BY id"); err != nil {
	log.Fatal(err) // sqlx：Rows.Scan 样板代码被压缩成 StructScan
}
// GORM：链式 API + AutoMigrate 自动建表
gdb.AutoMigrate(&UserGorm{})
gdb.Create(&UserGorm{Username: "carol", Password: "c"})
var u UserGorm
gdb.First(&u, "username = ?", "carol")
```

要点：**sqlx 是 database/sql 的"增强"而非替换**——`db tag` + `Select/Get/StructScan` 把列自动映射进结构体，连接池、事务、参数化 API 完全沿用，是学习成本最低的提效方案；**GORM 是全功能 ORM**——链式 API、AutoMigrate、回调，模型复杂时省事（本示例用 `github.com/glebarez/sqlite` 纯 Go 驱动跑通，验证状态见 examples/README.md）。**选型对比**：

| ORM | 风格 | 特点 | 适用场景 |
|-----|------|------|---------|
| database/sql | 原生 SQL | 零依赖、原理最清晰 | 学习原理、简单 CRUD |
| sqlx | 原生 SQL + 映射 | 轻量、几乎无学习成本 | 中小项目首选（本阶段推荐） |
| gorm | 全功能 ORM | 链式 API、自动迁移、回调 | 模型复杂、团队熟悉 ORM |
| ent | 代码生成 | schema 图定义、类型安全、编译期校验 | 大型团队、强类型偏好 |
| bun | SQL 优先 | 原生 SQL + query builder | 要 ORM 便利又要可控 SQL |

**坑：ORM 不是银弹**——复杂 JOIN、批量写入、报表查询仍要写原生 SQL；**坑：N+1 查询**——ORM 循环里逐条查关联（手写循环 QueryRow、gorm 不预加载时），1 条主查询 + N 条子查询，务必用 JOIN 或批量 `IN` 合并；gorm 的 `Updates` 默认不更新零值字段等行为差异务必读文档。ent/bun 未在本环境安装验证（选型表为背景知识）。

### 3.9 迁移（golang-migrate / goose）

```bash
# 本节全部命令未在本环境验证（本环境未安装 migrate/goose CLI，未实跑）
# 1. 安装 CLI
go install github.com/golang-migrate/migrate/v4/cmd/migrate@latest
# 2. 生成 create_users 迁移（.up.sql 与 .down.sql 成对）
migrate create -ext sql -dir migrations -seq create_users
# 3. 应用全部迁移
migrate -path migrations -database "sqlite://app.db" up
# 4. 回滚 1 个版本
migrate -path migrations -database "sqlite://app.db" down 1
# 5. 查看当前版本
migrate -path migrations -database "sqlite://app.db" version
```

```sql
-- migrations/000001_create_users.up.sql —— 应用
CREATE TABLE users (
  id         INTEGER PRIMARY KEY,
  username   TEXT NOT NULL UNIQUE,
  password   TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- migrations/000001_create_users.down.sql —— 回滚
DROP TABLE users;
```

要点：**迁移把 schema 变更版本化、进 git**——每个版本一对 `.up.sql`（应用）/`.down.sql`（回滚），`up` 应用、`down` 回滚、`version` 查当前版本。**坑：.down.sql 必须真正可回滚**——只写 up 不写 down 的"伪迁移"出事时无法回退；**坑：生产环境不手敲 ALTER TABLE**——全部走迁移文件 + CI（ph12）。golang-migrate / goose 的 CLI 工具未在本环境安装，本节命令标注「未在本环境验证」。

### 3.10 Redis 与 go-redis（String·Hash·Set·过期）

```go
// 完整可运行版见 examples/ex06-redis-cache/main.go
// 验证环境：go1.25.6 + go-redis v9.22.0（已验证，本机 Redis 16379）
ctx := context.Background()
rdb := redis.NewClient(&redis.Options{Addr: "127.0.0.1:16379"}) // 生产必设密码
defer rdb.Close()
if err := rdb.Ping(ctx).Err(); err != nil {
	panic(err)
}
rdb.Set(ctx, "user:1", "alice", 10*time.Minute) // String：缓存键值（带 TTL 过期）
v, _ := rdb.Get(ctx, "user:1").Result()
fmt.Println("String:", v)
rdb.HSet(ctx, "user:1:info", "name", "alice", "age", 18) // Hash：对象字段
age, _ := rdb.HGet(ctx, "user:1:info", "age").Int()
rdb.SAdd(ctx, "online:devices", "car-001", "car-002") // Set：去重集合（在线设备）
n, _ := rdb.SCard(ctx, "online:devices").Result()
rdb.Expire(ctx, "user:1", 30*time.Second) // 补设过期
rdb.Del(ctx, "user:1")
```

要点：**Redis 是内存数据结构服务器**——本阶段重点掌握 **String（缓存值/计数）、Hash（对象字段）、Set（去重集合/在线列表）**，List/ZSet 留给队列与排行榜（ph19）；**几乎所有命令都支持过期（TTL）**——`Set(key, val, ttl)` 或 `Expire`；go-redis 风格是"**命令链 + Result() 取值 + Err() 查错**"。**坑：忘记设过期时间 = 内存泄漏**——缓存键只增不减会把 Redis 撑爆；**坑：`redis.Nil` 表示键不存在**——它是"未命中"的正常信号不是 error，判断用 `errors.Is(err, redis.Nil)`（ex06 有完整用例）。

### 3.11 缓存策略（旁路缓存·穿透·击穿·雪崩）

```go
// 完整可运行版见 examples/ex06-redis-cache/main.go 的 getUser
// 验证环境：go1.25.6 + go-redis v9.22.0（已验证）
func getUser(ctx context.Context, db *sql.DB, rdb *redis.Client, id int64) (*User, error) {
	key := fmt.Sprintf("user:%d", id)
	raw, err := rdb.Get(ctx, key).Result()
	if err == nil { // ① 缓存命中
		if raw == "" {
			return nil, sql.ErrNoRows // 空值缓存命中：判定"不存在"
		}
		var u User
		if json.Unmarshal([]byte(raw), &u) == nil {
			return &u, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// ② Redis 故障：降级查库（缓存不致命）——记日志后继续走下面的查库分支
		log.Printf("Redis 故障（%v），降级查库", err)
	}
	var u User // ③ 未命中：查库
	if err := db.QueryRow("SELECT id, username FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			rdb.Set(ctx, key, "", 60*time.Second) // ④ 空值缓存防穿透
		}
		return nil, err
	}
	ttl := 10*time.Minute + time.Duration(id%30)*time.Second // ⑤ 随机抖动防雪崩
	data, _ := json.Marshal(u)
	rdb.Set(ctx, key, data, ttl) // ⑥ 回填
	return &u, nil
}
```

要点：**旁路缓存（Cache-Aside）是缓存策略的地基**——读路径"先缓存 → 未命中查库 → 回填"，写路径"先写库 → 删缓存"（删而非更新，避免脏数据）；三大经典问题的**基础解法**：**穿透**（查不存在的 key 打穿到库）→ 空值缓存；**击穿**（热点 key 过期瞬间并发打库）→ 互斥锁重建；**雪崩**（大量 key 同时过期）→ 过期时间加随机抖动（代码里 `id%30`）。**坑：缓存与数据库无法强一致**——本阶段掌握"写库删缓存 + 短 TTL"的最终一致，强一致属后续分布式阶段（见 4.4/第 5 章边界）。

### 3.12 慢查询与索引调优基础

```sql
-- MySQL：开慢日志（SQLite 用 EXPLAIN QUERY PLAN 观察执行计划）
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;  -- 超过 1 秒记入慢日志
EXPLAIN SELECT username FROM users WHERE username = 'alice';
-- key 列显示实际使用的索引；type: const/ref/range 好，ALL（全表扫描）差
```

```text
-- SQLite 的 EXPLAIN QUERY PLAN（ex01 实测输出）：
SEARCH users USING COVERING INDEX sqlite_autoindex_users_1 (username=?)
-- 命中 username 的 UNIQUE 索引 → 覆盖索引，无需回表
```

要点：**调优顺序：慢查询日志 → EXPLAIN → 建索引 → 改 SQL**；**索引失效的常见场景**——索引列做函数运算（`WHERE YEAR(created_at)=2024`）、前导通配符（`LIKE '%abc'`）、类型不匹配（字符串列传数字）。**坑：盲目加索引**——低区分度列（性别）不建、高频写表少建；**坑：SELECT \***——只取所需列，让覆盖索引生效（见 4.5）。

## 4. 底层原理

### 4.1 database/sql 的连接池与 driver 机制

- **driver 分离**：标准库 `database/sql/driver` 定义 Driver/Conn/Stmt 接口，modernc.org/sqlite、go-sql-driver/mysql、pgx 各自实现——`import _ "modernc.org/sqlite"` 只是注册（blank import 触发 init），业务代码里全是标准库类型
- **连接池 = 空闲队列 + 使用计数**：取连接优先复用空闲（LIFO），无空闲且未达 MaxOpenConns 则新建、已达上限则阻塞排队；用完归还——**只借不还（忘 Close）就是泄漏**，连接一直算"使用中"，池逐渐饿死；`db.Stats()` 的 InUse/Idle/WaitCount 就是观测这一机制的眼睛
- **事务独占连接**：`db.Begin()` 借一条连接并独占到 Commit/Rollback——事务里做慢查询会一直占住连接，所以**事务要短、快、不夹带无关操作**；这也解释了 3.6 的坑：裸写 `db.Exec("BEGIN")` 时连接池不知道你在开事务，可能把事务中的连接还回池子

### 4.2 事务的隔离级别与并发控制

- **ACID**：原子性（全成或全撤）、一致性（约束不破）、隔离性（并发互不干扰）、持久性（提交不丢）——Go 的 tx 把多条 SQL 绑到同一条连接上，是"原子性 + 隔离性"的最小单元
- **隔离级别**（松→严）：Read Uncommitted（脏读）→ Read Committed（防脏读）→ Repeatable Read（防不可重复读）→ Serializable（串行最严最慢）；**MySQL 默认 RR、PostgreSQL 默认 RC**——选级别是"一致性 vs 并发度"的权衡。Go 侧用 `db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})` 显式指定隔离级别（不指定则用驱动默认值）；`BeginTx` 相比 `Begin` 还能把 context 的取消/超时传进事务（project 的 BatchInsert 即用 `BeginTx(ctx, nil)`）
- **并发控制**：悲观锁（MySQL 的 `SELECT ... FOR UPDATE` 行锁）与乐观锁/条件更新（`UPDATE ... SET v=v-? WHERE v>=?`，冲突重试）——SQLite 不支持 FOR UPDATE，本阶段示例统一用条件更新，它在 MySQL/PostgreSQL 上同样成立（ex03 并发用例实测零超扣）；**坑：锁要尽早释放**——事务里锁的行越多越久并发越低，还容易死锁（全库保持一致的加锁顺序）

### 4.3 参数化查询的预编译（server-side prepare）

- **预编译（Prepared Statement）**：驱动先把 SQL 文本发给数据库编译成执行计划，占位符固定为参数位，之后每次执行只传值——**SQL 结构在执行前已定型，参数再"毒"也只是数据**
- 这才是参数化防注入的原理：拼接是"边拼边解析"，`' OR '1'='1` 会变成 SQL 语法；参数化是"先解析后填值"，注入文本永远进不了语法层
- **附带收益**：同一 SQL 重复执行免重新解析、数据库端可缓存执行计划；`db.Prepare` 显式预编译（3.4），`QueryRow("...?", args)` 由驱动自动 prepare——**日常用后者，循环批量插入用前者**

### 4.4 Redis 单线程模型与 pipeline

- **单线程事件循环**：Redis 所有命令由一个线程串行执行——无锁竞争、无上下文切换，单实例可达 10 万+ QPS；代价是**单个慢命令阻塞一切**：`KEYS *`、大 `HGETALL` 是生产禁忌，遍历用 `SCAN`
- **IO 多路复用**：epoll 监听海量连接、命令排队执行——"快"来自内存 + 单线程，而非多线程
- **pipeline**：一次 RTT 发送多条命令、一次收齐结果——批量操作必须用 `rdb.Pipelined(ctx, fn)`，逐条 Set 的网络开销差百倍；**坑：pipeline 不是事务**——中间命令失败不回滚，要原子性用 MULTI/EXEC（go-redis 的 TxPipelined）

### 4.5 索引 B+Tree 与慢查询

- **B+Tree**：InnoDB 的索引结构——非叶子节点只存"键 + 指针"（一页上千键、树高仅 3-4 层），叶子节点存数据且**双向链表相连**（范围查询友好）；一次查询 = 树高次磁盘 I/O，这就是索引快的根源
- **聚簇 vs 二级索引**：主键索引的叶子直接存整行（聚簇）；普通索引的叶子存主键值——**回表**（二级索引查到主键再回主键索引取行）多一次 I/O，所以"只查索引列"（覆盖索引）更快
- **慢查询链路**：慢日志 → EXPLAIN 看 `type`（ALL = 全表扫描最差）与 `key` → 建索引/改写 SQL；`LIMIT 100000, 10` 深分页也是大户，用"上一页最后 id"代替 OFFSET；SQLite 用 `EXPLAIN QUERY PLAN`，输出 `SEARCH ... USING INDEX` 即命中索引（ex01 有断言用例）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 用户注册登录落库 | database/sql CRUD、参数化、bcrypt 密码哈希 |
| 设备状态上报与查询 | INSERT/UPSERT、事务批量写入、索引、慢查询优化 |
| 转账/库存等资金操作 | 事务、条件更新防超扣、回滚 |
| 用户资料缓存加速 | Redis Hash、旁路缓存、TTL |
| 在线设备列表/去重 | Redis Set、SCard/SIsMember |
| 计数与限流 | Redis INCR + 过期（ph09 是内存滑动窗口限流，本阶段可升级为 Redis 分布式限流） |
| 接口热点数据加速 | 旁路缓存、击穿/雪崩防护 |
| 轨迹存储 | 批量写入 + 设备时间复合索引 + 最新位置缓存（见 project/） |
| schema 演进 | golang-migrate/goose 版本化迁移 |

**不适合**此阶段的事项：

- **分布式事务与多库一致性**（两阶段提交、Saga）：属后续阶段——本阶段单库单事务
- **消息队列与异步解耦**（Kafka/RabbitMQ/MQTT）：属 ph19 消息队列与事件驱动深入阶段
- **分库分表与读写分离集群**：属后续阶段——本阶段单库部署
- **大数据分析**（ClickHouse、离线数仓、ETL）：不属于本 roadmap 的 Go 主线

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64），驱动 **modernc.org/sqlite v1.57.0**（纯 Go 无 cgo；ex04 经 glebarez/sqlite v1.11.0 实际使用 v1.23.1，详见 examples/README.md）；全部示例已通过 `go vet ./...` 与 `go test ./...`，覆盖率实测见 examples/README.md 数据表。ex06 需要本机 Redis（127.0.0.1:16379，临时实例）。

### 示例 1：SQL 基础 + database/sql CRUD（ex01-sql-crud）

```go
// examples/ex01-sql-crud/main.go —— 参数化增删改查 + ErrNoRows + LastInsertId + EXPLAIN
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0，命令：go test -v ./...；go run .
func create(db *sql.DB, u *User) error { // 参数化 INSERT，LastInsertId 拿自增主键
	res, err := db.Exec("INSERT INTO users (username, password) VALUES (?, ?)", u.Username, u.Password)
	if err != nil {
		return err
	}
	u.ID, err = res.LastInsertId()
	return err
}
```

要点：CRUD 四条路径全参数化；`sql.ErrNoRows` 是"查无此记录"的唯一正确判定；重复 username 触发 UNIQUE 约束报错；`EXPLAIN QUERY PLAN` 实测命中覆盖索引。`go test -cover` 实测 **54.9%**。**完整文件**：`examples/ex01-sql-crud/`。

### 示例 2：连接池配置 + 预处理语句（ex02-connpool）

```go
// examples/ex02-connpool/main.go —— 四个 Set 方法 + db.Stats() + Prepare 批量插入
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0，命令：go test -v ./...
db.SetMaxOpenConns(10)
db.SetMaxIdleConns(5)
db.SetConnMaxLifetime(30 * time.Minute)
db.SetConnMaxIdleTime(5 * time.Minute)
```

要点：连接池四个参数 + Stats 观测；`db.Prepare` 批量插入与循环 Exec 对照（教学对照，性能差异用 Benchmark 体会）；并发 20 goroutine 写入在 MaxOpenConns=10 下排队不报错。`go test -cover` 实测 **50.0%**。**完整文件**：`examples/ex02-connpool/`。

### 示例 3：事务（转账提交/回滚 + 并发防超扣）（ex03-transaction）

```go
// examples/ex03-transaction/main.go —— Begin/Commit/Rollback + defer 兜底 + 条件更新
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0，命令：go test -v ./...；go test -race ./...
res, err := tx.Exec("UPDATE accounts SET balance = balance - ? WHERE username = ? AND balance >= ?",
	amount, from, amount)
if n, _ := res.RowsAffected(); n == 0 {
	return fmt.Errorf("余额不足: %s", from) // defer tx.Rollback() 自动回滚
}
```

要点：提交路径与回滚路径一目了然；并发防超扣实测 10 goroutine 转 1000 余额，最终总和不变、绝不为负（条件更新原子判断）；`defer tx.Rollback()` 防悬挂事务。`go test -cover` 实测 **52.2%**。**完整文件**：`examples/ex03-transaction/`。

### 示例 4：sqlx 与 GORM 选型对比（ex04-sqlx-gorm）

```go
// examples/ex04-sqlx-gorm/main.go —— 同一张表三种访问方式
// 验证环境：go1.25.6 + sqlx v1.4.0 / gorm v1.31.2，命令：go test -v ./...
db.Select(&users, "SELECT id, username, password FROM users ORDER BY id") // sqlx StructScan
gdb.AutoMigrate(&UserGorm{}); gdb.Create(&UserGorm{Username: "carol", Password: "c"}) // GORM
```

要点：database/sql（手写 Scan）→ sqlx（db tag + StructScan）→ GORM（AutoMigrate + 链式 API）三种写法对照；GORM 用纯 Go 驱动跑通；唯一约束与 Count 断言。`go test -cover` 实测 **41.7%**。**完整文件**：`examples/ex04-sqlx-gorm/`。

### 示例 5：并发访问数据库（ex05-concurrent）

```go
// examples/ex05-concurrent/main.go —— 20 goroutine 并发写 + 读，WAL + busy_timeout
// 验证环境：go1.25.6 + modernc.org/sqlite v1.57.0，命令：go test -race ./...
db, err := sql.Open("sqlite", "file:app.db?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
```

要点：并发写实测 200 条一条不丢；`go test -race` 干净（无数据竞争）；WAL 模式断言；busy_timeout 让写冲突排队而非报错。`go test -cover` 实测 **62.2%**。**完整文件**：`examples/ex05-concurrent/`。

### 示例 6：Redis 旁路缓存（ex06-redis-cache）

```go
// examples/ex06-redis-cache/main.go —— 旁路缓存三件套 + 空值缓存防穿透 + TTL 抖动
// 验证环境：go1.25.6 + go-redis v9.22.0 + 本机 Redis 16379，命令：先起 Redis，go test -v ./...
if err == nil { ... } else if !errors.Is(err, redis.Nil) { log.Printf("Redis 故障…降级查库") } // 命中/未命中/故障三分支
```

要点：查缓存 → 未命中查库 → 回填带 TTL；`errors.Is(err, redis.Nil)` 区分未命中与故障（故障降级查库，ex06 有 Redis 不可达时的降级用例）；空值缓存防穿透；写后删缓存；TTL 随机抖动防雪崩。`go test -cover` 实测 **48.0%**（Redis 可达时；不可达时 Redis 用例自动跳过）。**完整文件**：`examples/ex06-redis-cache/`。

## 7. 总结

### 关键要点

1. **先理解 database/sql，再选择 ORM**（必会概念）：连接池、事务、参数化、预处理的原理都在标准库，sqlx/gorm 只是语法糖
2. **SQL 注入必须通过参数化避免**（必会概念）：占位符 + 参数分离提交，动态值一律参数化，绝不拼接 SQL
3. **事务边界要由业务定义**（必会概念）：跨多条 SQL 的业务操作包进 Begin/Commit/Rollback，`defer tx.Rollback()` 防悬挂事务；防超扣用条件更新（跨库通用）
4. **连接池是性能与稳定性的闸门**：SetMaxOpenConns 设上限、SetConnMaxLifetime 换新连接、Rows/Stmt/Tx 用完即关防泄漏；db.Stats() 是观测窗口
5. **预处理把"解析"与"绑值"分离**：循环批量插入用 db.Prepare，单次查询用隐式 prepare；stmt 用完即关
6. **database/sql 并发安全、单连接不并发**：共享 *sql.DB、控制 MaxOpenConns；SQLite 靠 busy_timeout + WAL 撑并发写，race 检测必开
7. **缓存走旁路缓存 + TTL**：读"缓存 → 库 → 回填"、写"库 → 删缓存"；随机过期防雪崩、空值缓存防穿透、互斥锁防击穿
8. **Redis 是内存数据结构服务器**：单线程模型下禁 KEYS/大键；批量操作用 pipeline；过期时间必设；`redis.Nil` 是"未命中"不是错误
9. **索引是慢查询的第一解药**：EXPLAIN/EXPLAIN QUERY PLAN 看执行计划；函数运算、前导通配符、类型不匹配会让索引失效
10. **迁移把 schema 版本化**：up/down 成对、进 git、走 CI，生产不手改表结构
11. **显式处理三个特殊信号**：`sql.ErrNoRows`（查无）、`redis.Nil`（未命中）、`RowsAffected()==0`（更新未命中）

### 跨语言对比：数据库访问

| 维度 | Go database/sql | Java JDBC·MyBatis | Python SQLAlchemy | Node Prisma | Rust sqlx |
|------|-----------------|------------------|-------------------|-------------|----------|
| 基础 API | database/sql（标准库） | JDBC（标准库） | DB-API（标准库） | mysql2/pg 驱动 | sqlx（原生 SQL + 异步） |
| ORM/增强 | sqlx/gorm/ent/bun | MyBatis/Hibernate | SQLAlchemy/ORM | Prisma（schema 驱动） | diesel（ORM） |
| 参数化占位符 | `?` / `$1` | `?` / `#{}` | `:name` 绑定 | `$1` / `?` | `?` / `$1` |
| 事务 | tx.Begin/Commit/Rollback | 手动 setAutoCommit(false) | session.begin() | $transaction | tx.begin()/commit() |
| 连接池 | 内置（Set 方法） | HikariCP（第三方） | 内置 pool | 内置 pool | 内置 pool |
| 迁移 | golang-migrate/goose | Flyway/Liquibase | Alembic | prisma migrate | sqlx migrate |

### 阶段验收清单

- [ ] **能写参数化 SQL**：CRUD 全部占位符传参，能解释为什么能防注入，能识别拼接 SQL 的坏味道
- [ ] **能处理事务提交和回滚**：写得出 Begin/Commit/Rollback 的转账/库存代码，能演示"余额不足回滚"与"提交生效"两条路径
- [ ] **能防并发超扣**：条件更新或悲观锁方案，能解释为什么并发下余额不为负（ex03/sol-04 有可复现用例）
- [ ] **能配置并解释连接池**：四个 Set 方法各自作用，能讲出"连接泄漏 → 池耗尽"的因果链，会用 db.Stats() 观测
- [ ] **能使用预处理语句**：批量插入用 db.Prepare，能说出预编译防注入的原理（4.3）
- [ ] **能安全地并发访问数据库**：共享 *sql.DB、控制 MaxOpenConns，SQLite 下开 busy_timeout + WAL，race 检测通过
- [ ] **能完成 ORM 选型**：说清 database/sql / sqlx / gorm 的取舍，能指出 N+1 与"ORM 不是银弹"
- [ ] **能完成 Redis 基本操作**：String/Hash/Set 命令与过期、redis.Nil 的语义、pipeline 的用途
- [ ] **能设计基础缓存策略**：旁路缓存读写路径、TTL 与随机抖动、空值缓存防穿透，能说清缓存与数据库的一致性问题
- [ ] **能定位慢查询**：开慢日志、EXPLAIN 读执行计划、针对索引失效场景建索引

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap「练习」小节一一对应：

1. **用户表 CRUD**（★）：参数化增删改查 + ErrNoRows/RowsAffected 判定（提示：示例 1）
2. **设备状态存储**（★★）：批量 UPSERT + 事务整体回滚（提示：示例 3 的事务骨架 + 3.1 的 ON CONFLICT）
3. **Redis 缓存用户信息**（★★）：旁路缓存三件套 + TTL + 空值缓存（提示：示例 6）
4. **数据库事务处理**（★★★）：转账提交/回滚双路径 + 并发防超扣 + race（提示：示例 3）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**设备轨迹存储服务**——设备端定时上报 GPS 点落库（SQLite + 设备时间复合索引），Redis 缓存最新位置（旁路缓存，故障降级内存缓存），提供批量上报 / 最新位置 / 时间段轨迹三类接口。它是本阶段全部知识点的合体：批量事务写入（示例 3）+ 索引调优（4.5）+ 旁路缓存（示例 6）+ 连接池与 WAL（示例 5），也是 ph09 阶段项目「设备数据上报 API」的"落库升级"（ph09 数据存内存 map）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（go test / go vet / -race / 冒烟）

roadmap 另一个推荐项目「MySQL + Redis 的 Todo 服务」（Gin 接口 + 数据库持久化 + 列表缓存 + 用户归属 JOIN）可在完成后作为扩展：把 project/ 的存储层换表、加 users JOIN 与迁移文件即可。

### 下一阶段

[微服务与 RPC 阶段](../ph11-microservice-rpc/11-microservice-rpc.md) —— gRPC、protobuf、服务发现、API 网关；本阶段"单体 + 单库 + 单缓存"将拆分为多服务，服务间通信从 HTTP JSON 升级为 gRPC 二进制协议，本阶段学到的数据层能力（连接池、事务、索引）将下沉为各服务的独立存储。
