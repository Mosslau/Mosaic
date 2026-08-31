# exercises —— 数据库与缓存阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节一一对应：用户 CRUD、设备信息管理、车辆状态表、Redis 缓存查询结果。

完成顺序建议：按 1~4 顺序完成（逐步叠加：CRUD → 约束与索引 → 复合索引与批量写入 → 缓存旁路）。

## 依赖与验证方式

- 依赖：练习 1~3 只用**标准库 `sqlite3`**（零安装）；练习 4 需要 `pip install redis` + 本机 `redis-server`（本环境：redis-py 8.0.1 + redis-server 8.x 已装；alembic 未安装，本阶段迁移相关练习不要求装）
- 运行：`python3 sol-XX-*.py` 直接运行即自检（脚本内跑完整链路并打印结果）
- 产物纪律：sol 里所有数据库文件、redis 数据目录一律写到**系统临时目录**（`tempfile.mkdtemp`），redis-server 用随机端口 + 脚本结束 `terminate()` 干净关闭——运行后当前目录不得残留任何文件（`git status` 确认工作区干净）
- 参考实现文件头带**验证块**：环境、运行命令、实测输出（数字为本机实际运行结果）

## 练习 1：用户 CRUD（★）

- **目标**：用标准库 `sqlite3` 实现用户的增删改查四个函数并跑通
- **要求**：
  - 建表 `users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE)`
  - `create_user` / `get_user` / `update_user` / `delete_user` 四个函数，**值永远用 `?` 占位符**（参数化查询）；每个写操作后 `commit()`
  - 用 `' OR '1'='1` 这类恶意输入验证注入无效（查询命中 0 行）；重复 email 捕获 `sqlite3.IntegrityError` 后 `rollback()`
- **验收**：四函数返回正确（`create_user` 返回新主键、`update/delete` 返回受影响行数）；注入尝试命中 0 行；重复 email 抛错且事务已回滚

## 练习 2：设备信息管理（★★）

- **目标**：`devices` 表 + vin 唯一约束 + 索引，用 `EXPLAIN QUERY PLAN` 验证查询走索引
- **要求**：
  - 建表 `devices (id INTEGER PRIMARY KEY, vin TEXT NOT NULL UNIQUE, model TEXT NOT NULL, online INTEGER DEFAULT 0)`，注册设备时重复 vin 抛 `IntegrityError`（捕获后回滚）
  - 填充 2 万行后：① 按 `vin` 精确查询看执行计划（思考：为什么 UNIQUE 约束下不用建普通索引？）② 按非唯一列 `model` 查询，建 `CREATE INDEX idx_devices_model ON devices(model)` 前后对比执行计划与耗时
- **验收**：重复 vin 被拒；能说清 `UNIQUE` 自带索引（`sqlite_autoindex_*`）与普通索引的区别；`EXPLAIN QUERY PLAN` 输出从 `SCAN` 变为 `SEARCH ... USING INDEX`；能解释为什么小表上耗时差异不明显（数据都在页缓存里，见主文档 3.5）

## 练习 3：车辆状态表（★★）

- **目标**：`vehicle_status` 表高频批量写入 + 复合索引，验证最左前缀
- **要求**：
  - 建表 `vehicle_status (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, ts TEXT NOT NULL, status TEXT NOT NULL, speed REAL)`
  - 用 `executemany` 批量写入 **10 万行**（如 500 台车 × 200 条）；按 `(device_id, ts 范围)` 查询，建 `CREATE INDEX idx_status_device_ts ON vehicle_status(device_id, ts)` 前后对比执行计划与耗时
  - 单独按 `device_id` 查询，验证复合索引**最左前缀**生效
- **验收**：批量写入后行数为 10 万；有索引时执行计划为 `SEARCH ... USING INDEX`，耗时明显下降（本机实测约 21 倍）；`device_id` 单独查询也走 `idx_status_device_ts`

## 练习 4：Redis 缓存查询结果（★★★）

- **目标**：缓存旁路（cache-aside）模式缓存设备查询结果：TTL 过期 + 写库主动失效
- **要求**：
  - 用真实 `redis-server`（随机端口 + 临时目录起子进程，结束 `terminate()` 干净关闭）与 redis-py
  - `get_device_cached(device_id)`：先 `GET` 缓存，未命中查「库」（模拟 0.3s 慢查询）回填并 `set(key, json, ex=TTL)`；记录命中/未命中耗时
  - `update_device(...)`：写库后 **`DELETE` 缓存**（主动失效），下次读取必然 miss——防脏读
  - 验证：首次 miss → 二次 hit → 更新后 miss → 等 TTL 过期后 miss 四条路径
- **验收**：四条路径输出正确；hit 毫秒级、miss 约 0.3s（本机实测 hit 0.1 ms vs miss 305 ms，快约 3000 倍量级）；脚本结束 redis-server 干净关闭、当前目录无残留；能说清「过期（TTL）+ 淘汰（LRU）+ 主动失效」三个机制各管什么（主文档 4.5）

> **提示**：练习 1~4 与主文档 3.x 小节一一对应（3.1/3.2 SQL 与 sqlite3、3.5 索引、3.8 Redis 缓存）；做完后对照 `sol-*` 参考实现复盘——先独立完成，再看答案。
