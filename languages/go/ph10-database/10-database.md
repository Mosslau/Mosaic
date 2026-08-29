# Go 数据库阶段

> 面向后端服务、云原生和车联网数据平台方向，本阶段掌握 Go 操作数据库和缓存——SQL、连接池、事务、索引与 Redis，把"内存数据"升级为"可持久化、可并发、可上生产的存储"。

## 1. 概述

Go 数据库阶段的目标是：**能用 Go 操作数据库和缓存**——掌握 SQL 基础（MySQL/PostgreSQL）、database/sql 与 sqlx/gorm/ent/bun 选型、Redis 与 go-redis，并能配置连接池、编写事务、优化慢查询、做 schema 迁移。ph09 的接口全部把数据存在内存 map 里，本阶段把它们换成真实的 MySQL/Redis：用户登录后落库、设备状态持久化、热点数据进缓存。

| 核心维度 | 覆盖内容 |
|----------|---------|
| SQL 基础 | CRUD、WHERE、JOIN、索引概念（MySQL/PostgreSQL） |
| database/sql | sql.Open、Query/QueryRow/Exec、Scan、Rows 遍历 |
| 参数化查询 | 占位符 ?/$1、SQL 注入防御 |
| 连接池 | SetMaxOpenConns、SetMaxIdleConns、SetConnMaxLifetime |
| 事务 | Begin/Commit/Rollback、事务边界由业务定义 |
| sqlx 与 ORM | sqlx 结构体扫描、gorm/ent/bun 对比与选型 |
| Redis 与缓存 | go-redis、String/Hash/Set、过期时间、旁路缓存 |
| 工程化 | 迁移（golang-migrate/goose）、慢查询、索引调优 |

本阶段的核心信念是"**先理解 database/sql，再选择 ORM**"（必会概念）：database/sql 是标准库底座，连接池、事务、参数化的原理都在这里，sqlx/gorm 只是语法糖；**事务边界要由业务定义**——一个业务操作（如"下单减库存"）跨几条 SQL，就要包进同一个事务；**SQL 注入必须通过参数化避免**——动态值一律走占位符，绝不拼接 SQL 字符串。

范围边界：承接 ph09 Web 后端（内存 map 换数据库、JWT 用户落库、设备状态持久化）；**不涉及**微服务与 RPC（gRPC、服务发现属 ph11）、云原生部署（容器与 Kubernetes 属 ph12）、消息队列（Kafka/MQTT 属 ph19）、分布式事务（两阶段提交属 ph16）——本阶段是"单体服务 + 单库 + 单 Redis"。

## 2. 来源与演变

**database/sql 的"driver 分离"设计**：2012 年 database/sql 随 Go 1.0 进入标准库，效仿 net/http 的思路——标准库只定义统一 API 与 `database/sql/driver` 接口，具体数据库（MySQL、PostgreSQL、SQLite）由社区驱动实现。上层代码与数据库解耦：同一份代码换驱动即可切换数据库；这也是"先理解 database/sql"的缘由——它是所有访问方式的地基，连接池、事务、参数化都由它统一提供。

**ORM 生态的演进**：2013 年 **gorm** 出现（最流行的全功能 ORM，链式 API + 自动迁移）；2014 年 **sqlx** 出现（轻量增强，把 Rows.Scan 样板代码压缩成 `StructScan`）；2019 年 Facebook 开源 **ent**（图状 schema 定义 + 代码生成，类型安全）；2020 年 **bun** 出现（SQL 优先，支持 raw SQL 与 query builder）。选型路线：**database/sql 学原理 → sqlx 提效率 → 复杂模型用 gorm/ent**。

**Redis 与迁移工具**：Redis 2009 年发布，以"**单线程 + 内存数据结构 + 持久化**"成为缓存、锁与热点数据的标配；Go 客户端从 **redigo**（2012）演进到 **go-redis**（github.com/redis/go-redis，2021 年迁移组织名，v9 成主流），支持连接池、pipeline、pub/sub 与分布式锁。**迁移工具 golang-migrate（2017）与 goose（2013）** 把 schema 变更版本化：迁移文件进 git、CI 自动执行，是"数据库即代码"的基础。

| 时间 | 事件 |
|------|------|
| 2009 | Redis 发布（单线程内存数据存储） |
| 2012 | database/sql 随 Go 1.0 进入标准库（driver 分离设计） |
| 2012 | redigo 发布（Go 早期 Redis 客户端） |
| 2013 | gorm 发布；goose 迁移工具出现 |
| 2014 | sqlx 发布（结构体扫描简化） |
| 2017 | golang-migrate 发布（版本化迁移） |
| 2019 | Facebook 开源 ent（代码生成 ORM） |
| 2020 | bun 发布（SQL 优先 ORM） |
| 2021 | go-redis 迁移至 github.com/redis/go-redis，v9 成主流 |

## 3. 语法与参数

### 3.1 SQL 基础回顾（CRUD·WHERE·JOIN·索引概念）

```sql
CREATE TABLE users (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  username   VARCHAR(64)  NOT NULL UNIQUE,
  password   VARCHAR(128) NOT NULL,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
SELECT id, username FROM users WHERE id = 1;                  -- 读
INSERT INTO users (username, password) VALUES ('alice', 'x'); -- 增
UPDATE users SET password = 'y' WHERE id = 1;                 -- 改
DELETE FROM users WHERE id = 1;                               -- 删
SELECT u.username, d.speed FROM users u
  JOIN devices d ON d.user_id = u.id WHERE u.id = 2;          -- 关联
CREATE INDEX idx_users_username ON users(username);           -- 索引
```

要点：SQL 是声明式语言——**说"要什么"、不说"怎么做"**；`WHERE` 过滤、`JOIN` 关联、`ORDER BY/LIMIT` 排序分页；**索引是"书的目录"**——`WHERE`/`JOIN`/`ORDER BY` 命中的列建索引，但不是越多越好（占磁盘、拖慢写入）。**方言差异**：MySQL 占位符 `?`、自增 `AUTO_INCREMENT`；PostgreSQL 占位符 `$1`、自增 `SERIAL`——本阶段以 MySQL 为主、点出差异。

### 3.2 database/sql 核心（sql.Open·Query·QueryRow·Exec·Scan）

```go
package main
import (
	"database/sql"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql" // 驱动注册到 database/sql
)
func main() {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet?parseTime=true")
	if err != nil {
		log.Fatal(err) // Open 只校验 DSN 格式，不建立连接！
	}
	defer db.Close()
	if err := db.Ping(); err != nil { // Ping 才真正连库
		log.Fatal(err)
	}
	// QueryRow 单行 + Scan；Query 多行 + Rows 循环；Exec 增删改
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

要点：**`sql.Open` 不建连接、`db.Ping()` 才真正连库**——连接是惰性建立的；三个核心方法——**QueryRow 单行 + Scan、Query 多行 + Rows 循环、Exec 增删改**；`Scan` 按列顺序把值拷进指针。**坑：QueryRow 的 err 必须检查**——查无记录返回 `sql.ErrNoRows`，不检查就静默吞掉；**坑：Query 返回的 Rows 用完必须 Close**（`defer rows.Close()`），否则连接借了不还、连接池被耗尽（原理见 4.1）。

### 3.3 参数化查询与 SQL 注入防御

```go
package main
import (
	"database/sql"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql"
)
func main() {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	// 危险写法（反面教材）：username := "alice' OR '1'='1"
	// row := db.QueryRow("SELECT * FROM users WHERE username = '" + username + "'")
	username := "alice' OR '1'='1" // 恶意输入，参数化后只是普通字符串
	var id int64
	err = db.QueryRow("SELECT id FROM users WHERE username = ?", username).Scan(&id) // ? 占位符（PG 用 $1）
	if err != nil && err != sql.ErrNoRows {
		log.Fatal(err)
	}
	fmt.Println("查询结果 id =", id, "（注入未生效，返回空）")
}
```

要点：**参数化查询 = 占位符 + 参数分离提交**——驱动把参数作为"值"传给数据库，恶意内容永远是数据、进不了 SQL 语法层（原理见 4.3）；MySQL 用 `?`、PostgreSQL 用 `$1/$2`。**坑：一切拼接 SQL 字符串的行为都是注入入口**——包括表名、列名、排序字段（这些不能参数化，必须白名单校验）；**坑：以为"只有用户输入才危险"**——内部拼接同样危险，规范是"所有动态值一律参数化"。

### 3.4 连接池配置（SetMaxOpenConns 等）

```go
package main
import (
	"database/sql"
	"time"
	_ "github.com/go-sql-driver/mysql"
)
func newDB(dsn string) (*sql.DB, error) { // database/sql 自带连接池
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(50)                  // 最大打开连接数（含使用中）
	db.SetMaxIdleConns(25)                  // 最大空闲连接数（常驻待命）
	db.SetConnMaxLifetime(30 * time.Minute) // 单条连接最长存活
	db.SetConnMaxIdleTime(5 * time.Minute)  // 空闲超时即回收
	return db, nil
}
func main() {
	db, err := newDB("root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		panic(err)
	}
	defer db.Close()
}
```

要点：**database/sql 自带连接池**，四个 Set 方法就是全部配置；**SetMaxOpenConns 是并发上限**——超过后请求排队，防数据库被打爆；**SetConnMaxLifetime 防"连接老化"**——MySQL 的 wait_timeout 会断空闲连接，定期换新连接规避"连接已死"报错。**坑：连接池耗尽**——handler 里忘 `rows.Close()`、事务不结束，连接只借不还，达到 MaxOpenConns 后所有请求卡死；**坑：OpenConns 设太小**（如 2）高并发吞吐骤降——按 `QPS × 单查询耗时` 估算。

### 3.5 事务（Begin·Commit·Rollback·Tx 边界）

```go
package main
import (
	"database/sql"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql"
)
// transfer 转账：扣款 + 加款原子完成（事务边界由业务定义：必会概念）
func transfer(db *sql.DB, fromID, toID int64, amount int64) error {
	tx, err := db.Begin() // ① 开启事务
	if err != nil {
		return err
	}
	defer tx.Rollback() // ② 兜底：Commit 前任何 return 都自动回滚，防"悬挂事务"
	var balance int64
	if err := tx.QueryRow("SELECT balance FROM accounts WHERE id = ? FOR UPDATE", fromID).Scan(&balance); err != nil {
		return err
	}
	if balance < amount {
		return fmt.Errorf("余额不足: 余额 %d < 转账 %d", balance, amount)
	}
	if _, err := tx.Exec("UPDATE accounts SET balance = balance - ? WHERE id = ?", amount, fromID); err != nil {
		return err
	}
	if _, err := tx.Exec("UPDATE accounts SET balance = balance + ? WHERE id = ?", amount, toID); err != nil {
		return err
	}
	return tx.Commit() // ③ 全部成功才提交
}
func main() {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := transfer(db, 1, 2, 100); err != nil {
		log.Println(err)
	}
}
```

要点：**事务边界由业务定义**（必会概念）——"转账"跨"扣款 + 加款"两条 SQL，必须包进同一个事务：全部成功 Commit、任一步失败 Rollback；**`defer tx.Rollback()` 是防泄漏标配**——Commit 成功后它是空操作，但中间任何 return 都保证回滚。**坑：只 Commit 不处理错误 / 忘记 Rollback**——留下"悬挂事务"占用连接与行锁；**`FOR UPDATE` 是行级悲观锁**，防止并发转账超扣（乐观锁见 4.2）。

### 3.6 sqlx 增强与 ORM 选型（gorm/ent/bun）

```go
package main
import (
	"fmt"
	"log"
	"github.com/jmoiron/sqlx" // go get github.com/jmoiron/sqlx
	_ "github.com/go-sql-driver/mysql"
)
type User struct {
	ID       int64  `db:"id"`
	Username string `db:"username"`
	Password string `db:"password"`
}
func main() {
	db, err := sqlx.Connect("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet?parseTime=true")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	var users []User
	if err := db.Select(&users, "SELECT * FROM users WHERE id > ?", 0); err != nil { // db tag 自动映射列
		log.Fatal(err)
	}
	fmt.Printf("%+v\n", users)
}
```

要点：**sqlx 是 database/sql 的"增强"而非替换**——`db tag` + `Select/Get/StructScan` 把列自动映射进结构体，连接池、事务、参数化 API 完全沿用，是学习成本最低的提效方案。**选型对比**：

| ORM | 风格 | 特点 | 适用场景 |
|-----|------|------|---------|
| database/sql | 原生 SQL | 零依赖、原理最清晰 | 学习原理、简单 CRUD |
| sqlx | 原生 SQL + 映射 | 轻量、几乎无学习成本 | 中小项目首选（本阶段推荐） |
| gorm | 全功能 ORM | 链式 API、自动迁移、回调 | 模型复杂、团队熟悉 ORM |
| ent | 代码生成 | schema 图定义、类型安全、编译期校验 | 大型团队、强类型偏好 |
| bun | SQL 优先 | 原生 SQL + query builder | 要 ORM 便利又要可控 SQL |

**坑：ORM 不是银弹**——复杂 JOIN、批量写入、报表查询仍要写原生 SQL；**坑：N+1 查询**——ORM 循环里逐条查关联（手写循环 QueryRow、gorm 不预加载时），1 条主查询 + N 条子查询，务必用 JOIN 或批量 `IN` 合并；gorm 的 `Updates` 默认不更新零值字段等行为差异务必读文档。

### 3.7 迁移（golang-migrate / goose）

```bash
# go install github.com/golang-migrate/migrate/v4/cmd/migrate@latest
# migrate create -ext sql -dir migrations -seq create_users   # 生成 .up.sql 与 .down.sql
# migrate -path migrations -database "mysql://root:123456@tcp(127.0.0.1:3306)/tenet" up
# migrate -path migrations -database "mysql://root:123456@tcp(127.0.0.1:3306)/tenet" down 1
# migrate -path migrations -database "mysql://root:123456@tcp(127.0.0.1:3306)/tenet" version
```

```sql
-- migrations/000001_create_users.up.sql —— 应用
CREATE TABLE users (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  username   VARCHAR(64) NOT NULL UNIQUE,
  password   VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- migrations/000001_create_users.down.sql —— 回滚
DROP TABLE users;
```

要点：**迁移把 schema 变更版本化、进 git**——每个版本一对 `.up.sql`（应用）/`.down.sql`（回滚），`up` 应用、`down` 回滚、`version` 查当前版本。**坑：.down.sql 必须真正可回滚**——只写 up 不写 down 的"伪迁移"出事时无法回退；**坑：生产环境不手敲 ALTER TABLE**——全部走迁移文件 + CI（ph12）。

### 3.8 Redis 与 go-redis（String·Hash·Set·过期）

```go
package main
import (
	"context"
	"fmt"
	"time"
	"github.com/redis/go-redis/v9" // go get github.com/redis/go-redis/v9
)
func main() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: "127.0.0.1:6379", Password: ""}) // 生产必设密码
	defer rdb.Close()
	if err := rdb.Ping(ctx).Err(); err != nil {
		panic(err)
	}
	rdb.Set(ctx, "user:1", "alice", 10*time.Minute) // String：缓存键值（带 TTL 过期）
	v, _ := rdb.Get(ctx, "user:1").Result()
	fmt.Println("String:", v)
	rdb.HSet(ctx, "user:1:info", "name", "alice", "age", 18) // Hash：对象字段
	age, _ := rdb.HGet(ctx, "user:1:info", "age").Int()
	fmt.Println("Hash age:", age)
	rdb.SAdd(ctx, "online:devices", "car-001", "car-002") // Set：去重集合（在线设备）
	n, _ := rdb.SCard(ctx, "online:devices").Result()
	fmt.Println("在线设备数:", n)
	rdb.Expire(ctx, "user:1", 30*time.Second)
	rdb.Del(ctx, "user:1")
}
```

要点：**Redis 是内存数据结构服务器**——本阶段重点掌握 **String（缓存值/计数）、Hash（对象字段）、Set（去重集合/在线列表）**，List/ZSet 留给队列与排行榜（ph19）；**几乎所有命令都支持过期（TTL）**——`Set(key, val, ttl)` 或 `Expire`；go-redis 风格是"**命令链 + Result() 取值 + Err() 查错**"。**坑：忘记设过期时间 = 内存泄漏**——缓存键只增不减会把 Redis 撑爆；**坑：`redis.Nil` 表示键不存在**——它是"未命中"的正常信号不是 error，判断用 `errors.Is(err, redis.Nil)`。

### 3.9 缓存策略（旁路缓存·过期·击穿·雪崩）

```go
package main
import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
	"github.com/redis/go-redis/v9"
)
// 旁路缓存（Cache-Aside）：读→先查缓存，未命中→查库→回填缓存
func getUser(ctx context.Context, db *sql.DB, rdb *redis.Client, id int64) (string, error) {
	key := fmt.Sprintf("user:%d", id)
	if v, err := rdb.Get(ctx, key).Result(); err == nil {
		return v, nil // 缓存命中
	} else if !errors.Is(err, redis.Nil) {
		return "", err // Redis 故障：降级查库，缓存不致命
	}
	var name string
	if err := db.QueryRow("SELECT username FROM users WHERE id = ?", id).Scan(&name); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			rdb.Set(ctx, key, "", 60*time.Second) // 空值缓存，防穿透
		}
		return "", err
	}
	// 回填缓存：TTL 加随机抖动，防雪崩
	rdb.Set(ctx, key, name, 10*time.Minute+time.Duration(id%30)*time.Second)
	return name, nil
}
func main() {
	fmt.Println("旁路缓存完整可运行版见\"示例 3\"") // 本段演示模式，依赖真实 DB/Redis
}
```

要点：**旁路缓存（Cache-Aside）是缓存策略的地基**——读路径"先缓存 → 未命中查库 → 回填"，写路径"先写库 → 删缓存"（删而非更新，避免脏数据）；三大经典问题的**基础解法**：**穿透**（查不存在的 key 打穿到库）→ 空值缓存；**击穿**（热点 key 过期瞬间并发打库）→ 互斥锁重建；**雪崩**（大量 key 同时过期）→ 过期时间加随机抖动（代码里 `id%30`）。**坑：缓存与数据库无法强一致**——本阶段掌握"写库删缓存 + 短 TTL"的最终一致，强一致属 ph16 分布式事务。完整可运行版见"示例 3"。

### 3.10 慢查询与索引调优基础

```sql
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;  -- 超过 1 秒记入慢日志
EXPLAIN SELECT username FROM users WHERE username = 'alice';
-- key 列显示实际使用的索引；type: const/ref/range 好，ALL（全表扫描）差
```

要点：**调优顺序：慢查询日志 → EXPLAIN → 建索引 → 改 SQL**；**索引失效的常见场景**——索引列做函数运算（`WHERE YEAR(created_at)=2024`）、前导通配符（`LIKE '%abc'`）、类型不匹配（字符串列传数字）。**坑：盲目加索引**——低区分度列（性别）不建、高频写表少建；**坑：SELECT \***——只取所需列，让覆盖索引生效（见 4.5）。

## 4. 底层原理

### 4.1 database/sql 的连接池与 driver 机制

- **driver 分离**：标准库 `database/sql/driver` 定义 Driver/Conn/Stmt 接口，go-sql-driver/mysql、pgx、mattn/go-sqlite3 各自实现——`import _ "github.com/go-sql-driver/mysql"` 只是注册，业务代码里全是标准库类型
- **连接池 = 空闲队列 + 使用计数**：取连接优先复用空闲（LIFO），无空闲且未达 MaxOpenConns 则新建、已达上限则阻塞排队；用完归还——**只借不还（忘 Close）就是泄漏**，连接一直算"使用中"，池逐渐饿死
- **事务独占连接**：`db.Begin()` 借一条连接并独占到 Commit/Rollback——事务里做慢查询会一直占住连接，所以**事务要短、快、不夹带无关操作**

### 4.2 事务的隔离级别与 Go 的 Tx 抽象

- **ACID**：原子性（全成或全撤）、一致性（约束不破）、隔离性（并发互不干扰）、持久性（提交不丢）——Go 的 tx 把多条 SQL 绑到同一条连接上，是"原子性 + 隔离性"的最小单元
- **隔离级别**（松→严）：Read Uncommitted（脏读）→ Read Committed（防脏读）→ Repeatable Read（防不可重复读）→ Serializable（串行最严最慢）；**MySQL 默认 RR、PostgreSQL 默认 RC**——选级别是"一致性 vs 并发度"的权衡
- **并发控制**：悲观锁（`SELECT ... FOR UPDATE` 行锁，示例 2/4 采用）与乐观锁（`UPDATE ... SET v=v+1 WHERE v=?`，冲突重试）；**坑：锁要尽早释放**——事务里锁的行越多越久并发越低，还容易死锁（全库保持一致的加锁顺序）

### 4.3 参数化查询的预编译（server-side prepare）

- **预编译（Prepared Statement）**：驱动先把 SQL 文本发给数据库编译成执行计划，占位符固定为参数位，之后每次执行只传值——**SQL 结构在执行前已定型，参数再"毒"也只是数据**
- 这才是参数化防注入的原理：拼接是"边拼边解析"，`' OR '1'='1` 会变成 SQL 语法；参数化是"先解析后填值"，注入文本永远进不了语法层
- **附带收益**：同一 SQL 重复执行免重新解析、数据库端可缓存执行计划；`db.Prepare` 显式预编译，`QueryRow("...?", args)` 由驱动自动 prepare——**日常用后者，循环批量插入用前者**

### 4.4 Redis 单线程模型与 pipeline

- **单线程事件循环**：Redis 所有命令由一个线程串行执行——无锁竞争、无上下文切换，单实例可达 10 万+ QPS；代价是**单个慢命令阻塞一切**：`KEYS *`、大 `HGETALL` 是生产禁忌，遍历用 `SCAN`
- **IO 多路复用**：epoll 监听海量连接、命令排队执行——"快"来自内存 + 单线程，而非多线程
- **pipeline**：一次 RTT 发送多条命令、一次收齐结果——批量操作必须用 `rdb.Pipelined(ctx, fn)`，逐条 Set 的网络开销差百倍；**坑：pipeline 不是事务**——中间命令失败不回滚，要原子性用 MULTI/EXEC（go-redis 的 TxPipelined）

### 4.5 索引 B+Tree 与慢查询

- **B+Tree**：InnoDB 的索引结构——非叶子节点只存"键 + 指针"（一页上千键、树高仅 3-4 层），叶子节点存数据且**双向链表相连**（范围查询友好）；一次查询 = 树高次磁盘 I/O，这就是索引快的根源
- **聚簇 vs 二级索引**：主键索引的叶子直接存整行（聚簇）；普通索引的叶子存主键值——**回表**（二级索引查到主键再回主键索引取行）多一次 I/O，所以"只查索引列"（覆盖索引）更快
- **慢查询链路**：慢日志 → EXPLAIN 看 `type`（ALL = 全表扫描最差）与 `key` → 建索引/改写 SQL；`LIMIT 100000, 10` 深分页也是大户，用"上一页最后 id"代替 OFFSET

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 用户注册登录落库 | database/sql CRUD、参数化、bcrypt 密码哈希 |
| 设备状态上报与查询 | INSERT/UPSERT、索引、慢查询优化 |
| 转账/库存等资金操作 | 事务、FOR UPDATE 行锁、回滚 |
| 用户资料缓存加速 | Redis Hash、旁路缓存、TTL |
| 在线设备列表/去重 | Redis Set、SCard/SIsMember |
| 计数与限流 | Redis INCR + 过期（ph09 限流的 Redis 实现） |
| 接口热点数据加速 | 旁路缓存、击穿/雪崩防护 |
| schema 演进 | golang-migrate/goose 版本化迁移 |

**不适合**此阶段的事项：

- **分布式事务与多库一致性**（两阶段提交、Saga）：属 ph16——本阶段单库单事务
- **消息队列与异步解耦**（Kafka/RabbitMQ/MQTT）：属 ph19
- **分库分表与读写分离集群**：属后续阶段——本阶段单库部署
- **大数据分析**（ClickHouse、离线数仓、ETL）：不属于本 roadmap 的 Go 主线

## 6. 代码示例

### 示例 1：用户表 CRUD（database/sql 参数化 + 扫描到结构体）

```go
// 依赖: go get github.com/go-sql-driver/mysql
// 建表: CREATE DATABASE tenet DEFAULT CHARSET utf8mb4;
//   CREATE TABLE users (id BIGINT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(64) NOT NULL UNIQUE,
//   password VARCHAR(128) NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);
package main
import (
	"database/sql"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql"
)
type User struct {
	ID       int64
	Username string
	Password string
}
var db = mustDB()
func mustDB() *sql.DB {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet?parseTime=true")
	if err != nil {
		log.Fatal(err)
	}
	db.SetMaxOpenConns(50)
	db.SetMaxIdleConns(10)
	return db
}
func create(u *User) error { // 参数化 INSERT，LastInsertId 拿自增主键
	res, err := db.Exec("INSERT INTO users (username, password) VALUES (?, ?)", u.Username, u.Password)
	if err != nil {
		return err
	}
	u.ID, _ = res.LastInsertId()
	return nil
}
func getByID(id int64) (*User, error) {
	u := &User{}
	err := db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username, &u.Password)
	return u, err
}
func updatePassword(id int64, pwd string) error {
	_, err := db.Exec("UPDATE users SET password = ? WHERE id = ?", pwd, id)
	return err
}
func deleteByID(id int64) error {
	_, err := db.Exec("DELETE FROM users WHERE id = ?", id)
	return err
}
func main() {
	u := &User{Username: "alice", Password: "p@ss"}
	if err := create(u); err != nil {
		log.Fatal(err)
	}
	fmt.Println("创建:", u.ID)
	if err := updatePassword(u.ID, "new-pwd"); err != nil {
		log.Fatal(err)
	}
	got, err := getByID(u.ID)
	if err == sql.ErrNoRows {
		fmt.Println("不存在")
	} else if err != nil {
		log.Fatal(err)
	} else {
		fmt.Printf("查询: %+v\n", got)
	}
	if err := deleteByID(u.ID); err != nil {
		log.Fatal(err)
	}
	fmt.Println("删除完成")
}
```

要点：roadmap 练习**用户表 CRUD** 的完整答案——C（INSERT + LastInsertId）/R（QueryRow + Scan）/U（Exec UPDATE）/D（Exec DELETE）四条路径全参数化；**`sql.ErrNoRows` 是"查无此记录"的唯一正确判定**；**坑：password 字段真实项目存 bcrypt 哈希**（`golang.org/x/crypto/bcrypt`），绝不存明文。验证前先执行注释里的建表 SQL，并确认本机 MySQL 账号密码与 DSN 一致。

### 示例 2：设备状态存储（事务：批量更新 + 回滚演示）

```go
// 依赖: go get github.com/go-sql-driver/mysql
// 建表: CREATE TABLE device_status (id BIGINT AUTO_INCREMENT PRIMARY KEY,
//   device_id VARCHAR(64) NOT NULL UNIQUE, status VARCHAR(16) NOT NULL,
//   speed DOUBLE NOT NULL DEFAULT 0,
//   updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP);
package main
import (
	"database/sql"
	"errors"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql"
)
type DeviceStatus struct {
	DeviceID string
	Status   string
	Speed    float64
}
// batchUpsert 一批设备状态一次性写入：全部成功才提交，任一条失败整体回滚
func batchUpsert(db *sql.DB, items []DeviceStatus) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback() // 防"事务未回滚"的兜底
	for _, it := range items {
		if it.DeviceID == "" {
			return errors.New("device_id 不能为空") // 中间出错 → defer 回滚
		}
		_, err := tx.Exec(
			"INSERT INTO device_status (device_id, status, speed) VALUES (?, ?, ?) "+
				"ON DUPLICATE KEY UPDATE status = VALUES(status), speed = VALUES(speed)",
			it.DeviceID, it.Status, it.Speed)
		if err != nil {
			return err
		}
	}
	return tx.Commit() // 全部成功才提交
}
func main() {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	ok := []DeviceStatus{{"car-001", "online", 88.5}, {"car-002", "online", 60}}
	fail := []DeviceStatus{{"car-003", "online", 0}, {"", "offline", 0}} // 第二条非法
	if err := batchUpsert(db, ok); err != nil {
		log.Fatal(err)
	}
	fmt.Println("批量写入成功（2 条）")
	if err := batchUpsert(db, fail); err != nil {
		fmt.Println("批量写入失败，已整体回滚:", err)
	}
}
```

要点：roadmap 练习**设备状态存储**的完整答案——**车机批量上报场景**（每台车每秒一条，逐条 INSERT 性能差，批量 + UPSERT 一次往返完成）；事务演示两条路径——`ok` 数据 Commit 生效、`fail` 数据因第二条 device_id 为空**整批回滚**（验证：`SELECT COUNT(*) FROM device_status` 只有 2 条）；**坑：事务里 return 前必须回滚**，`defer tx.Rollback()` 一行解决；**坑：`ON DUPLICATE KEY UPDATE` 依赖 UNIQUE 索引**——建表时 device_id 必须 UNIQUE。

### 示例 3：Redis 缓存用户信息（旁路缓存 + 过期）

```go
// 依赖: go get github.com/redis/go-redis/v9 github.com/go-sql-driver/mysql
// 需要本机 Redis 与示例 1 的 users 表；先执行: INSERT INTO users (username, password) VALUES ('bob', 'x');
package main
import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"
	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"
)
type User struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
}
// getUser 旁路缓存：先 Redis，未命中查 MySQL 并回填
func getUser(ctx context.Context, db *sql.DB, rdb *redis.Client, id int64) (*User, error) {
	key := fmt.Sprintf("user:%d", id)
	raw, err := rdb.Get(ctx, key).Result()
	if err == nil { // 缓存命中
		if raw == "" {
			return nil, sql.ErrNoRows // 空值缓存命中：判"不存在"
		}
		var u User
		if json.Unmarshal([]byte(raw), &u) == nil {
			return &u, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		return nil, err // Redis 故障：降级查库
	}
	var u User
	if err := db.QueryRow("SELECT id, username FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			rdb.Set(ctx, key, "", 60*time.Second) // 空值缓存防穿透
		}
		return nil, err
	}
	ttl := 10*time.Minute + time.Duration(id%30)*time.Second // 随机抖动防雪崩
	data, _ := json.Marshal(u)
	rdb.Set(ctx, key, data, ttl)
	return &u, nil
}
func main() {
	ctx := context.Background()
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	rdb := redis.NewClient(&redis.Options{Addr: "127.0.0.1:6379"})
	defer rdb.Close()
	u, err := getUser(ctx, db, rdb, 1) // 第一次：查库回填
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("用户:", u.Username)
	u2, err := getUser(ctx, db, rdb, 1) // 第二次：缓存命中
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("再次读取（缓存命中）:", u2.Username)
}
```

要点：roadmap 练习**Redis 缓存用户信息**的完整答案——旁路缓存三件套"**查缓存 → 未命中查库 → 回填带 TTL**"；**json 序列化存对象**（比存多个 String 键更省 Redis 往返）；**`errors.Is(err, redis.Nil)` 区分"未命中"与"Redis 故障"**——故障要降级放行查库，缓存不致命；**坑：缓存键要带业务前缀 + ID 命名空间**（`user:1`），防跨业务冲突。

### 示例 4：数据库事务处理（转账/库存，提交与回滚路径）

```go
// 依赖: go get github.com/go-sql-driver/mysql
// 建表: CREATE TABLE accounts (id BIGINT AUTO_INCREMENT PRIMARY KEY,
//   username VARCHAR(64) NOT NULL UNIQUE, balance BIGINT NOT NULL DEFAULT 0);
//   INSERT INTO accounts (username, balance) VALUES ('alice', 1000), ('bob', 500);
package main
import (
	"database/sql"
	"errors"
	"fmt"
	"log"
	_ "github.com/go-sql-driver/mysql"
)
// Transfer 转账：扣款 + 加款原子完成；余额不足则回滚
func Transfer(db *sql.DB, from, to string, amount int64) error {
	if amount <= 0 {
		return errors.New("转账金额必须为正") // 事务外的前置校验
	}
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback() // 提交前任何 return 都回滚
	var balance int64
	err = tx.QueryRow("SELECT balance FROM accounts WHERE username = ? FOR UPDATE", from).Scan(&balance)
	if err == sql.ErrNoRows {
		return errors.New("转出账户不存在")
	}
	if err != nil {
		return err
	}
	if balance < amount {
		return fmt.Errorf("余额不足: %s 只有 %d", from, balance)
	}
	if _, err := tx.Exec("UPDATE accounts SET balance = balance - ? WHERE username = ?", amount, from); err != nil {
		return err
	}
	if _, err := tx.Exec("UPDATE accounts SET balance = balance + ? WHERE username = ?", amount, to); err != nil {
		return err
	}
	return tx.Commit() // 提交路径：两条 UPDATE 一起生效
}
func main() {
	db, err := sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := Transfer(db, "alice", "bob", 200); err != nil {
		log.Fatal(err) // 提交路径
	}
	fmt.Println("转账成功: alice -200, bob +200")
	if err := Transfer(db, "alice", "bob", 99999); err != nil {
		fmt.Println("回滚路径:", err) // 余额不足 → 事务回滚
	}
	var a, b int64
	db.QueryRow("SELECT balance FROM accounts WHERE username='alice'").Scan(&a)
	db.QueryRow("SELECT balance FROM accounts WHERE username='bob'").Scan(&b)
	fmt.Printf("校验: alice=%d bob=%d（总和不变）\n", a, b)
}
```

要点：roadmap 练习**数据库事务处理**的完整答案——提交路径（余额充足，Commit 生效）与回滚路径（余额不足，defer Rollback，**两条 UPDATE 都不生效**）一目了然；**`FOR UPDATE` 锁住 from 行**，并发转账同一账户不会超扣（悲观锁）；**坑：事务边界必须覆盖业务全流程**——"查询余额 → 判断 → 扣款 → 加款"任何一步在事务外，都会出现"查了余额却没扣成"的中间态；**坑：前置校验（金额为正）放事务外提前挡掉**，减少无谓事务开销；扩展：库存扣减用带条件更新 `UPDATE stock SET count = count - ? WHERE id = ? AND count >= ?`。

### 示例 5：MySQL + Redis 的 Todo 服务（ph09 Web 基础 + 持久化 + 缓存）

```go
// 运行: go mod init todo-db && go get github.com/gin-gonic/gin github.com/go-sql-driver/mysql github.com/redis/go-redis/v9 && go run .
// 建表: CREATE TABLE todos (id BIGINT AUTO_INCREMENT PRIMARY KEY,
//   text VARCHAR(255) NOT NULL, done TINYINT(1) NOT NULL DEFAULT 0,
//   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);
// 本机需 MySQL + Redis；按实际环境改 DSN 与 Redis 地址
package main
import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"time"
	"github.com/gin-gonic/gin"
	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"
)
type Todo struct {
	ID   int64  `json:"id"`
	Text string `json:"text"`
	Done bool   `json:"done"`
}
var (
	db  *sql.DB
	rdb *redis.Client
)
func main() {
	var err error
	db, err = sql.Open("mysql", "root:123456@tcp(127.0.0.1:3306)/tenet?parseTime=true")
	if err != nil {
		panic(err)
	}
	rdb = redis.NewClient(&redis.Options{Addr: "127.0.0.1:6379"})
	r := gin.Default()
	r.GET("/todos", listTodos)
	r.POST("/todos", createTodo)
	r.PATCH("/todos/:id/done", markDone)
	r.Run("127.0.0.1:8080")
}
func listTodos(c *gin.Context) {
	ctx := c.Request.Context()
	key := "todos:list"
	if raw, err := rdb.Get(ctx, key).Bytes(); err == nil { // 缓存命中
		c.Data(http.StatusOK, "application/json", raw)
		return
	}
	rows, err := db.QueryContext(ctx, "SELECT id, text, done FROM todos ORDER BY id")
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()
	todos := []Todo{}
	for rows.Next() {
		var t Todo
		if err := rows.Scan(&t.ID, &t.Text, &t.Done); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		todos = append(todos, t)
	}
	raw, err := json.Marshal(todos) // 未命中：查库 → 回填缓存
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	rdb.Set(ctx, key, raw, 30*time.Second)
	c.Data(http.StatusOK, "application/json", raw)
}
func createTodo(c *gin.Context) {
	var req struct {
		Text string `json:"text" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "text 不能为空"})
		return
	}
	res, err := db.ExecContext(c.Request.Context(), "INSERT INTO todos (text) VALUES (?)", req.Text)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	id, _ := res.LastInsertId()
	rdb.Del(c.Request.Context(), "todos:list") // 写路径：删缓存保一致
	c.JSON(http.StatusCreated, Todo{ID: id, Text: req.Text})
}
func markDone(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "id 必须是整数"})
		return
	}
	res, err := db.ExecContext(c.Request.Context(), "UPDATE todos SET done = 1 WHERE id = ?", id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if n, _ := res.RowsAffected(); n == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "todo not found"})
		return
	}
	rdb.Del(c.Request.Context(), "todos:list")
	c.JSON(http.StatusOK, gin.H{"id": id, "done": true})
}
```

要点：roadmap 推荐项目 **MySQL + Redis 的 Todo 服务**的最小完整实现——**ph09 的 Gin 接口原样保留，只把内存 map 换成 MySQL（增删改查全参数化）+ Redis（列表旁路缓存）**；**读路径"先缓存 → 未命中查库 → 回填"、写路径"写库 → 删缓存"**正是 3.9 的旁路缓存落地；**QueryContext/ExecContext 把请求 context 传给数据库**——ph09 的超时中间件自动生效，请求取消时查询即中断。**坑：列表缓存要短 TTL + 写后删缓存**，否则新增/完成操作后列表陈旧；**坑：`RowsAffected()==0` 判定不存在**——UPDATE 未影响行 = id 不存在，别只靠 err。扩展：补 DELETE 接口、给 Todo 加用户归属（关联 users 表）、用 Redis INCR 做每用户限流（ph09 限流的 Redis 版）。

## 7. 总结

### 关键要点

1. **先理解 database/sql，再选择 ORM**（必会概念）：连接池、事务、参数化的原理都在标准库，sqlx/gorm 只是语法糖
2. **SQL 注入必须通过参数化避免**（必会概念）：占位符 + 参数分离提交，动态值一律参数化，绝不拼接 SQL
3. **事务边界要由业务定义**（必会概念）：跨多条 SQL 的业务操作包进 Begin/Commit/Rollback，`defer tx.Rollback()` 防悬挂事务
4. **连接池是性能与稳定性的闸门**：SetMaxOpenConns 设上限、SetConnMaxLifetime 换新连接、Rows/Stmt 用完即关防泄漏
5. **缓存走旁路缓存 + TTL**：读"缓存 → 库 → 回填"、写"库 → 删缓存"；随机过期防雪崩、空值缓存防穿透、互斥锁防击穿
6. **Redis 是内存数据结构服务器**：单线程模型下禁 KEYS/大键；批量操作用 pipeline；过期时间必设
7. **索引是慢查询的第一解药**：EXPLAIN 看 type/key；函数运算、前导通配符、类型不匹配会让索引失效
8. **迁移把 schema 版本化**：up/down 成对、进 git、走 CI，生产不手改表结构
9. **数据库不是强一致的银弹**：缓存与库的最终一致靠"删缓存 + 短 TTL"，强一致属 ph16 分布式事务
10. **显式处理三个特殊信号**：`sql.ErrNoRows`（查无）、`redis.Nil`（未命中）、`RowsAffected()==0`（更新未命中）

### 跨语言对比：数据库访问

| 维度 | Go database/sql | Java JDBC·MyBatis | Python SQLAlchemy | Node Prisma | Rust sqlx |
|------|-----------------|------------------|-------------------|-------------|----------|
| 基础 API | database/sql（标准库） | JDBC（标准库） | DB-API（标准库） | mysql2/pg 驱动 | sqlx（原生 SQL + 异步） |
| ORM/增强 | sqlx/gorm/ent/bun | MyBatis/Hibernate | SQLAlchemy/ORM | Prisma（schema 驱动） | diesel（ORM） |
| 参数化占位符 | `?` / `$1` | `?` / `#{}` | `:name` 绑定 | `$1` / `?` | `?` / `$1` |
| 事务 | tx.Begin/Commit/Rollback | 手动 setAutoCommit(false) | session.begin() | $transaction | tx.begin()/commit() |
| 连接池 | 内置（Set 方法） | HikariCP（第三方） | 内置 pool | 内置 pool | 内置 pool |
| 迁移 | golang-migrate/goose | Flyway/Liquibase | Alembic | prisma migrate | sqlx migrate |

### 阶段验收标准

- **能写参数化 SQL**：CRUD 全部占位符传参，能解释为什么能防注入，能识别拼接 SQL 的坏味道
- **能处理事务提交和回滚**：写得出 Begin/Commit/Rollback 的转账/库存代码，能演示"余额不足回滚"与"提交生效"两条路径
- **能设计基础缓存策略**：旁路缓存读写路径、TTL 与随机抖动、空值缓存防穿透，能说清缓存与数据库的一致性问题
- **能配置并解释连接池**：四个 Set 方法各自作用，能讲出"连接泄漏 → 池耗尽"的因果链
- **能完成 Redis 基本操作**：String/Hash/Set 命令与过期、redis.Nil 的语义、pipeline 的用途
- **能定位慢查询**：开慢日志、EXPLAIN 读执行计划、针对索引失效场景建索引

### 进入下一阶段前

确保能完成以下练习（均来自 roadmap，对应示例编号）：

- **用户表 CRUD**：参数化增删改查 + 扫描到结构体（提示：示例 1；补"用户名唯一冲突"的错误处理与 bcrypt 密码哈希）
- **设备状态存储**：批量 UPSERT + 事务，演示整体回滚（提示：示例 2；扩展按 device_id 建索引并用 EXPLAIN 验证）
- **Redis 缓存用户信息**：旁路缓存三件套 + TTL（提示：示例 3；扩展用 Hash 存用户字段、随机过期时间）
- **数据库事务处理**：转账提交/回滚双路径 + FOR UPDATE 行锁（提示：示例 4；扩展库存扣减 `count >= ?` 条件更新与乐观锁版本号）
- **Todo 服务落库**：把 ph09 示例 1 的内存 Todo 换成 MySQL + Redis（提示：示例 5；补 DELETE 与分页查询 `LIMIT ? OFFSET ?` 的参数化写法）
- **迁移初体验**：用 golang-migrate 给 Todo 服务加一张表并 up/down 往返（提示：3.7 的命令；观察 version 变化）

### 推荐项目

- **MySQL + Redis 的 Todo 服务**：Gin 接口 + MySQL 持久化 + Redis 列表缓存 + 用户归属（users 表 JOIN）+ 迁移文件管理 schema——覆盖本阶段全部知识点，是 ph09 Todo API 的"数据库版升级"，验收时用 curl 验证 CRUD 并重启服务确认数据不丢
- **车辆轨迹存储服务**：车机端定时上报 GPS 点（device_id、lat、lng、speed、ts），MySQL 按"设备 + 时间"建索引存轨迹，Redis 缓存"最新位置"（旁路缓存 + 短 TTL），提供"查最新位置 / 查某设备某时间段轨迹"接口——把示例 2（批量写入）+ 示例 3（缓存）+ 索引调优（4.5）拼成车联网场景的完整服务，正是 roadmap 推荐项目的形态

### 下一阶段

**微服务与 RPC 阶段**（`ph11-microservice-rpc`，文档规划中）——gRPC、protobuf、服务发现、API 网关、分布式基础；本阶段"单体 + 单库 + 单 Redis"将拆分为多服务，服务间通信从 HTTP JSON 升级为 gRPC 二进制协议，数据库访问下沉为各服务的独立数据层。
