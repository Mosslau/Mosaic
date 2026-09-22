# ph10 数据库阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），四题与 roadmap 本阶段「练习」小节一一对应（用户表 CRUD / 设备状态存储 / Redis 缓存用户信息 / 数据库事务处理）。按 roadmap 顺序 1 → 2 → 3 → 4 即可，按难度递进建议 1 → 2 → 4 → 3。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod + go.sum），先进入对应目录再运行（如 `cd sol-01-user-crud && go test -v`）。请勿在 exercises/ 根目录执行 `go test ./...`——根目录没有 go.mod。

数据库驱动：**modernc.org/sqlite v1.57.0**（纯 Go 无 cgo）。sol-03 需要本机 Redis（端口 16379，临时实例），Redis 不可达时其测试自动跳过。依赖拉取环境：`GOPROXY=https://goproxy.cn,direct GOSUMDB=off GOCACHE=/tmp/gocache`（本机默认 proxy.golang.org 不可达，goproxy.cn 可达）。参考实现文件头都写了验证环境与命令（已验证：go1.25.6，darwin/arm64）。

## 练习 1：用户表 CRUD（★）

**目标**：用 database/sql + 参数化 SQL 实现 users 表增删改查，覆盖"不存在"与"重复用户名"两条错误路径。

**要求**：

- 建表：`users(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)`
- C：参数化 INSERT，用 `LastInsertId` 拿回自增主键
- R：`QueryRow + Scan` 单行查询；查无记录返回 `sql.ErrNoRows`（用 `errors.Is` 判断）
- U：参数化 UPDATE，用 `RowsAffected()==0` 判定"更新未命中"
- D：参数化 DELETE，同样用 `RowsAffected` 判定
- 所有 SQL 一律占位符 `?` 传参，禁止字符串拼接；密码字段真实项目存 bcrypt 哈希（本练习可先存明文，验收不要求）

**验收**：`go test -v` 全部通过，覆盖：创建返回自增 ID、按 ID 查询、查不存在返回 ErrNoRows、重复 username 插入报错、更新/删除存在与不存在的记录；`go vet ./...` 零报告。

> 提示：参考 examples/ex01-sql-crud；内存库 `sql.Open("sqlite", ":memory:")` 即可，测试建表放 `t.Cleanup` 关闭连接。

## 练习 2：设备状态存储（★★）

**目标**：设备状态批量写入 + 事务整体回滚，理解"事务边界由业务定义"。

**要求**：

- 建表：`device_status(device_id TEXT PRIMARY KEY, status TEXT NOT NULL, speed REAL NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)`
- `BatchUpsert(items []DeviceStatus) error`：一个事务里逐条 `INSERT ... ON CONFLICT(device_id) DO UPDATE SET status=excluded.status, speed=excluded.speed`
- 任一条 `device_id` 为空 → 返回错误且**整批回滚**（验证：COUNT 不变）
- 全部合法 → 提交，COUNT 等于批内条数
- `defer tx.Rollback()` 兜底，禁止手动裸写 `BEGIN`（会与连接池冲突）

**验收**：`go test -v` 覆盖：合法批量写入全部生效、含非法条目的批次整体回滚（事务前 COUNT == 事务后 COUNT）、重复 device_id 的 upsert 更新旧值；`go vet ./...` 零报告。

> 提示：参考 examples/ex03-transaction 的事务骨架 + SQLite 的 `ON CONFLICT(device_id) DO UPDATE`（MySQL 对应 `ON DUPLICATE KEY UPDATE`，方言差异见阶段笔记 3.1）。

## 练习 3：Redis 缓存用户信息（★★）

**目标**：用 go-redis 实现旁路缓存三件套——查缓存 → 未命中查库 → 回填带 TTL。

**要求**：

- Redis 地址 `127.0.0.1:16379`（测试不可达时自动跳过，不硬失败）
- `GetUser(ctx, db, rdb, id)`：先 `rdb.Get`，命中直接返回；`errors.Is(err, redis.Nil)` 才是未命中（Redis 故障要降级查库，缓存不致命）
- 未命中查 SQLite `users` 表并回填：JSON 序列化 + TTL `10min + id%30 秒` 随机抖动防雪崩
- 查无此用户 → 缓存空串 60 秒（空值缓存防穿透）
- 提供 `Invalidate(ctx, rdb, id)`：删缓存（写路径用）

**验收**：`go test -v` 覆盖：首次读取查库回填且缓存 key 出现、二次读取命中缓存、不存在的 id 触发空值缓存、TTL 在预期区间、删缓存后 key 消失；`go vet ./...` 零报告。

> 提示：参考 examples/ex06-redis-cache；测试前先起 Redis：`redis-server --port 16379 --save '' --appendonly no --daemonize yes`，测完 `redis-cli -p 16379 shutdown nosave`。

## 练习 4：数据库事务处理（★★★）

**目标**：转账提交/回滚双路径 + **并发防超扣**，理解悲观锁与条件更新的取舍。

**要求**：

- 建表：`accounts(username TEXT PRIMARY KEY, balance INTEGER NOT NULL)`
- `Transfer(db, from, to string, amount int64) error`：先校验 `amount > 0`；事务内扣款 + 加款；任一步失败整体回滚
- **防超扣必须用条件更新**：`UPDATE accounts SET balance = balance - ? WHERE username = ? AND balance >= ?`，`RowsAffected()==0` 即余额不足（SQLite 不支持 `FOR UPDATE`；MySQL 可用 `SELECT ... FOR UPDATE` 悲观锁，见阶段笔记 4.2）
- 加款目标账户不存在时不报错（`UPDATE` 匹配 0 行），由业务侧自行决定是否校验
- 并发测试：10 个 goroutine 各转 100，初始余额 1000——最终余额总和必须等于 1000、绝不出现负余额

**验收**：`go test -v` 覆盖提交路径（余额变化正确）、回滚路径（余额不变）、非法金额、并发防超扣（断言 `alice+bob == 1000` 且 `alice >= 0`）；`go test -race ./...` 干净；`go vet ./...` 零报告。

> 提示：参考 examples/ex03-transaction；并发写要开 `busy_timeout`（DSN `file:xxx.db?_pragma=busy_timeout(5000)`），否则并发会报 `database is locked`。

---

四道练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
