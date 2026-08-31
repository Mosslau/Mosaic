# ph11 阶段项目：设备管理后端（数据层）

> 对应 Roadmap（python.md）ph11「推荐项目」第一个「设备管理后端」。devices 表（vin 唯一约束）＋ device_status 状态表（复合索引）＋ 用户 CRUD ＋ 手写迁移脚本演进结构 ＋ 缓存设备热点查询（TTL 过期 + 写库主动失效）——示例 1/3/4/5 的合体，也是 ph10 设备管理 API 的数据层升级。

## 需求

实现一个设备管理后端的数据层：用户 CRUD（参数化查询防注入、email 唯一约束）；设备注册（vin 唯一约束，重复注册拒绝）；车辆状态高频批量写入（`executemany`）与按设备 + 时间窗口查询（`(device_id, ts)` 复合索引）；按设备分组统计（count / avg_speed / max_speed）；设备热点查询走缓存（缓存旁路 + TTL 过期 + 写库主动失效防脏读）。表结构由**手写迁移脚本**（`schema_version`）从 v1 逐步演进到 v4——结构变更可版本化、可重放、失败回滚。数据库用 SQLite（标准库 `sqlite3`，零第三方依赖），呼应本阶段「SQL 基础比 ORM 更重要」的必会概念。

## 功能清单

- [x] 迁移：`MIGRATIONS` 按版本顺序应用（v1 users → v2 devices → v3 device_status → v4 复合索引），幂等（重复执行跳过已应用版本）、每个版本一个事务、失败整体回滚
- [x] 用户 CRUD：`UserRepo.create/get/update/delete`，参数化查询（`?` 占位符）、email 唯一约束、写操作后 `commit()`
- [x] 设备注册：`DeviceRepo.register`（vin 唯一约束自带索引，重复 vin 抛 `IntegrityError`）、`set_online`、`get_by_vin`
- [x] 状态入库与查询：`StatusRepo.ingest_batch`（`executemany` 批量）、`query`（设备 + 可选时间窗口 + limit，走复合索引）、`stats`（按设备分组：count / avg_speed / max_speed，可只统计单台）
- [x] 缓存：`TTLCache`（TTL 过期 + 惰性删除 + 命中统计），`DeviceService.get_device` 缓存旁路（miss 查库回填）、`update_device` 写库后删缓存（主动失效防脏读）
- [x] CLI：`--demo` 离线演示全链路（临时库：迁移 → 用户 CRUD → 3 台设备注册 → 72 条状态批量入库 → 窗口查询 → 分组统计 → 缓存 miss/hit/失效/过期 → 自检，退出码 0）
- [x] 测试：`tests/test_device_manager.py` 离线覆盖迁移幂等 / 建表 / 用户 CRUD / email 唯一 / vin 唯一 / 批量入库 / 窗口查询 / 分组统计 / 缓存 TTL / 缓存失效 / CLI（pytest 13 用例）
- [x] 质量：`pyproject.toml` 内置 ruff 配置，`ruff check . && pytest -q` 一键门禁（本环境实测：ruff 零告警、pytest 13 用例全过）

## 验收标准

- [ ] `python3 device_manager.py --demo` 离线跑通：迁移到 schema v4、用户 CRUD 返回正确、重复 vin 被拒、72 条状态入库（3 车 × 24 条）、分组统计 count=24/avg/max 数字正确、缓存 hits=3 / misses=3、自检通过、退出码 0
- [ ] `pytest -q` 全部通过（13 用例，离线、不依赖网络与第三方库）；`ruff check .` 零告警
- [ ] 数据库文件只出现在系统临时目录（`tempfile.mkdtemp`），运行后 `git status` 工作区干净
- [ ] 能说清：`schema_version` 迁移为什么幂等且失败不留半成品（主文档 3.7）；复合索引 `(device_id, ts)` 最左前缀怎么生效（主文档 3.5）；缓存「过期 + 主动失效」各防什么问题（主文档 4.5）

## 扩展方向（可选）

- 换 SQLAlchemy + Alembic：模型用 `Mapped` 风格（ph10 3.7），迁移交给 `alembic revision --autogenerate` + `upgrade head`——本机 alembic 未安装，故本项目用手写 `schema_version` 等价实现（见 examples/ex05-migration.py）
- 换真实 Redis：`TTLCache` 换成 redis-py 的 `get/set(ex=)/delete`（redis-py 8.0.1 + redis-server 已在本环境安装，落法见 exercises/sol-04-redis-cache.py 与 examples/ex06-redis-cache.py），再补 `maxmemory-policy=allkeys-lru` 淘汰策略
- 暴露为 HTTP 接口：把 `DeviceService`/`StatusRepo` 接进 ph10 的设备管理 FastAPI（依赖注入 `yield` Session 生命周期管理），批量上报 + 查询 + 统计直接复用
- 状态查询加时间桶聚合（`strftime` + `GROUP BY` 按小时/天分组），向 ph12+ 自动化脚本阶段的时间序列报表过渡

## 验证环境

- Python 3.13.9；核心零第三方依赖（标准库 `sqlite3` 与 `time`/`tempfile`；测试：pytest 8.4.2、ruff 0.12.0）
- 安装：`pip install pytest ruff`（建议先在 venv 中安装，见 ph07）
- 运行：`python3 device_manager.py --demo`；测试：`pytest -q`；门禁：`ruff check . && pytest -q`
- 验证状态：已验证（`--demo` 退出码 0、pytest 13 用例全过、ruff 零告警，均在本环境实际执行通过）

`--demo` 实测输出（节选，数据库在临时目录）：

```text
迁移完成 -> schema 版本: 4 （users / devices / device_status / 复合索引 共 4 步）
用户 CRUD -> create id: 1 | update rowcount: 1 | get: {'id': 1, 'name': 'Alice2', 'email': 'alice@example.com'}
重复 vin 被拒 -> UNIQUE constraint failed: devices.vin
状态批量入库 -> 72 条（3 车 × 24 条）
按设备+时间窗口查询 -> 3 条，首条 speed: 50.0
分组统计 -> [{'device_id': 1, 'count': 24, 'avg_speed': 55.3, 'max_speed': 60.5}, ...]
缓存 -> hits: 2 misses: 1 | r3 cached: True
写库主动失效后 -> misses: 2 | r5 cached: True
TTL 过期后 -> misses: 3 | r6 cached: False
自检通过：3 台设备、72 条状态、缓存 hit/miss 计数正确
```
