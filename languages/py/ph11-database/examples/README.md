# examples —— 数据库与缓存阶段完整示例

> 每个示例对应主文档 `11-database.md` 相关小节（3.x / 4.x / 6 章）的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：sqlite3（标准库，零安装）、sqlalchemy 2.0.43、redis-py 8.0.1 + redis-server 8.x（本机已装；alembic **未安装**，对应能力以概念讲解 + 手写等价实现呈现，见 ex05 说明）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-sqlite-crud.py` | 用户 CRUD：标准库 sqlite3 建表 + 增删改查 + 参数化查询 + 唯一约束（主文档 3.1/3.2、roadmap 示例） | `python3 ex01-sqlite-crud.py`（离线） |
| `ex02-transaction.py` | 事务与失败回滚：转账保证一致性边界，含 SAVEPOINT 嵌套回滚（主文档 3.4/4.2） | `python3 ex02-transaction.py`（离线） |
| `ex03-index-query-plan.py` | 索引与查询优化：`EXPLAIN QUERY PLAN` + 两万行实测耗时对比（主文档 3.5/4.1） | `python3 ex03-index-query-plan.py`（离线） |
| `ex04-sqlalchemy.py` | SQLAlchemy 2.0：Core `text()` + ORM `Mapped`/`Session` + `echo` 看 SQL + 连接池参数与池状态（主文档 3.3/3.6） | `python3 ex04-sqlalchemy.py`（离线） |
| `ex05-migration.py` | 迁移脚本：手写 `schema_version` 迁移（版本化、幂等、失败回滚）——alembic 未安装，此为同思想等价实现（主文档 3.7） | `python3 ex05-migration.py`（离线） |
| `ex06-redis-cache.py` | Redis 缓存：真实 redis-server（临时端口 + 临时目录）演示 string/TTL/EXPIRE + 缓存旁路命中耗时（主文档 3.7/4.5） | `python3 ex06-redis-cache.py`（离线） |

说明：

- **产物纪律**：全部示例的数据库文件（`.db`）与 redis 数据目录都写到**系统临时目录**（`tempfile.mkdtemp`），脚本结束自动回收（ex06 `shutil.rmtree`）；运行后用 `git status` 可确认工作区干净。
- **ex06 是唯一启动真实服务的示例**：脚本内 `subprocess.Popen` 起一个 `redis-server` 子进程（端口随机、`--save ''` 不持久化、数据目录在临时目录），结束时 `terminate()` + `wait()` 干净关闭——不留进程、不留文件，与 ph10 示例 2 的「进程内起服务 → 干净关闭」同一纪律。
- **依赖状态**：sqlalchemy 2.0.43 与 redis-py 8.0.1 在本环境已安装并实测；redis-server 本机已装（`/opt/homebrew/bin/redis-server`）；alembic **未安装**（`python3 -c "import alembic"` 报 ModuleNotFoundError）——ex05 用手写 `schema_version` 演示同一套迁移思想，装好 alembic 后由 `alembic revision --autogenerate` + `alembic upgrade head` 接管（概念见主文档 3.7）。

验证状态：全部示例均已在本环境实际运行通过（已验证）。实测关键输出：

- `ex01`：`create_user -> id: 1`；批量后总行数 `3`；重复 email 抛 `IntegrityError`（UNIQUE constraint failed: users.email）；`update_user` rowcount `1`；`delete_user` rowcount `1`、剩余 `2`
- `ex02`：初始 `[('A', 1000.0), ('B', 0.0)]`；转账 2000 失败回滚后余额不变；转账 300 成功后 `[('A', 700.0), ('B', 300.0)]`；SAVEPOINT 回滚只撤销 savepoint 之后的操作
- `ex03`：两万行按 vin 查询——无索引执行计划 `SCAN devices`、耗时 `0.34 ms`；加索引后 `SEARCH devices USING INDEX idx_devices_vin (vin=?)`、耗时 `0.02 ms`（约 17 倍差距）
- `ex04`：Core `text()` 查询 `[('Alice',)]`；ORM `echo=True` 打印生成的 `INSERT`/`SELECT`；池状态从「Connections in pool: 0」到「借出 1 条后 Checked out: 1」再到「归还后 pool: 1」
- `ex05`：v1~v4 按序应用、当前版本 `4`；再次执行跳过全部（幂等）；含 v2/v4 列的数据插入成功
- `ex06`：`SET + GET` 返回 JSON；TTL `60` 秒、`EXPIRE` 调为 `120`；缓存旁路——首次 `miss 302 ms` → 第二次 `hit 0.1 ms`（快 3086 倍）→ TTL 过期后重新 `miss 305 ms`；脚本结束打印「redis-server 已关闭，临时目录已回收」
