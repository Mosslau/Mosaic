# examples —— 数据库阶段完整示例

验证环境：go1.25.6（darwin/arm64）。六个示例各自是**独立的 Go module**（目录内自带 go.mod + go.sum），先进入示例目录再运行——请勿在 examples/ 根目录执行 `go test ./...`（根目录没有 go.mod）。

数据库驱动策略：全部示例用 **modernc.org/sqlite v1.57.0**（纯 Go、无 cgo，`database/sql` 的 SQLite 驱动）——本环境网络经 `GOPROXY=https://goproxy.cn` 拉取依赖并实际跑通。MySQL/PostgreSQL 是生产主选（go-sql-driver/mysql、pgx），但需要独立数据库服务器，本环境未启动，故示例统一落在 SQLite 上；SQL 方言差异（`?` vs `$1`、`FOR UPDATE` 等）在阶段笔记 3.x 与 4.x 中点出。ex06 需要本机 Redis（端口 16379，临时实例）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-sql-crud/` | SQL 基础 + database/sql CRUD：参数化增删改查、LastInsertId、sql.ErrNoRows、Rows 循环、EXPLAIN QUERY PLAN 看索引 | `cd ex01-sql-crud && go test -v`；`go run .` |
| `ex02-connpool/` | 连接池：四个 Set 方法 + db.Stats() 观测 + db.Prepare 预处理批量插入（与循环 Exec 对照） | `cd ex02-connpool && go test -v`；`go run .` |
| `ex03-transaction/` | 事务：转账 Begin/Commit/Rollback + defer 回滚兜底 + 条件更新（UPDATE ... WHERE balance >= ?）防并发超扣 | `cd ex03-transaction && go test -v`；`go run .` |
| `ex04-sqlx-gorm/` | ORM 对比：同一张表用 database/sql、sqlx（StructScan）与 GORM（AutoMigrate + 链式 API）三种方式访问 | `cd ex04-sqlx-gorm && go test -v`；`go run .` |
| `ex05-concurrent/` | 并发访问数据库：20 goroutine 并发写 + 读，busy_timeout + WAL 防锁冲突，`go test -race` 验证无数据竞争 | `cd ex05-concurrent && go test -race ./...`；`go run .` |
| `ex06-redis-cache/` | Redis 旁路缓存（go-redis）：查缓存 → 未命中查库 → 回填 TTL、空值缓存防穿透、写后删缓存 | 先起 Redis（见下），`cd ex06-redis-cache && go test -v`；`go run .` |

ex06 的 Redis 准备（本机需有 redis-server；本环境实测用的正是这个临时实例）：

```bash
# 1. 启动临时 Redis（端口 16379，无持久化，测完杀掉）
redis-server --port 16379 --save '' --appendonly no --daemonize yes
# 2. 运行示例
cd ex06-redis-cache && go test -v
# 3. 测完清理
redis-cli -p 16379 shutdown nosave
```

## 实测数据（本环境跑出，如实记录）

全部示例通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go test ./...`（行为符合预期）；覆盖率为本机实际输出（`go test -cover`）：

| 示例 | go test -cover | 备注 |
|------|----------------|------|
| ex01-sql-crud | 54.9% | 6 个用例全过（CRUD 全路径 + ErrNoRows + 重复用户名 + 执行计划） |
| ex02-connpool | 50.0% | 5 个用例全过（池配置 + 预处理 + 对照 + 并发 20 goroutine） |
| ex03-transaction | 52.2% | 5 个用例全过（提交/回滚/非法金额/缺失账户/并发防超扣） |
| ex04-sqlx-gorm | 41.7% | 6 个用例全过（database/sql + sqlx + GORM CRUD/唯一约束/计数 + via* 全流程） |
| ex05-concurrent | 62.2% | 4 个用例全过；`go test -race ./...` 干净（无数据竞争） |
| ex06-redis-cache | 46.0% | 4 个用例全过（命中/未命中空值缓存/删缓存/TTL）；Redis 实测可达 |

> ⚠️ ex06 的覆盖率是 Redis 可达时实测的；Redis 不可达时相关用例自动 t.Skip，覆盖率会下降——以「验证状态」列的标注为准。

## 注意事项

- 文件库示例（ex02/ex03/ex04/ex05）把数据库文件写到 `/tmp/`（`exXX-*.db`），不污染仓库；内存库示例（ex01/ex06）用 `:memory:`。测试一律用 `t.TempDir()`。
- 全部示例的驱动版本：**modernc.org/sqlite v1.57.0**（ex04 另含 sqlx v1.4.0、gorm.io/gorm v1.31.2 + glebarez/sqlite v1.11.0；ex06 另含 go-redis v9.22.0）。
- 依赖拉取环境：`GOPROXY=https://goproxy.cn,direct GOSUMDB=off GOCACHE=/tmp/gocache`（本机默认 proxy.golang.org 不可达，goproxy.cn 可达）。
- 六个示例的验证状态均为：**已验证（go1.25.6 + modernc.org/sqlite v1.57.0）**，ex06 额外要求 Redis。
