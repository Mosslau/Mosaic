# ph10 阶段项目：设备数据上报 API

> 对应 Roadmap（python.md）ph10「推荐项目」第二个「设备数据上报 API」。设备遥测上报接口 `POST /telemetry`（请求体校验：速度 0~200、SOC 0~100），按设备/时间查询与统计（结合 ph09 分组统计思维），支持批量写库，日志中间件记录每条上报的耗时与状态码。

## 需求

实现一个设备遥测数据上报服务：设备侧把 `(device_id, ts, speed, soc)` 上报进来，服务端做参数校验（速度 0~200、SOC 0~100，超限 422）后写库；提供按设备/时间的查询接口与分组统计接口（不传设备 ID 按设备分组返回 count/avg_speed/max_speed/avg_soc，呼应 ph09 的 groupby 思维）；每个请求经日志中间件记录"方法 + 路径 + 状态码 + 耗时"，错误路径全部输出结构化 JSON。数据库用 SQLite 起步（正式项目换 PostgreSQL，见 ph11），Session 由依赖注入管理（防连接池泄漏）。

## 功能清单

- [x] 上报：`POST /telemetry` 单条（201，返回带 `id` 的完整记录）；`POST /telemetry/batch` 批量（1~1000 条，任意一条非法整体 422；空列表 400）
- [x] 校验：`TelemetryIn`（`speed` 0~200、`soc` 0~100、`device_id` 限长、`ts` ISO 8601）——非法输入自动 422 结构化错误
- [x] 查询：`GET /telemetry` 按 `device_id` / `since` / `until` / `limit` 过滤，按时间升序
- [x] 统计：`GET /telemetry/stats` 不传 `device_id` 按设备分组，传了只统计该设备（`count` / `avg_speed` / `max_speed` / `avg_soc`）
- [x] 横切：日志中间件（方法 + 路径 + 状态码 + 耗时）、统一错误处理（`HTTPException`/校验错误/兜底 500 均 JSON）
- [x] ORM 与生命周期：SQLAlchemy 2.0 `Mapped` 风格模型 + 依赖注入 `yield` Session（每请求一个、用完自动关，主文档 4.4）
- [x] CLI：`--demo` 离线演示全链路（临时库：批量 72 条 → 非法上报 422 → 查询 → 分组统计 → 自检）
- [x] 测试：`tests/test_telemetry_api.py` 离线覆盖上报/校验/批量/过滤/统计/CLI（pytest 7 用例）
- [x] 质量：`pyproject.toml` 内置 ruff 配置（含 FastAPI 的 `Depends`/`Query` 白名单），`ruff check . && pytest -q` 一键门禁

## 验收标准

- [ ] `python3 telemetry_api.py --demo` 离线跑通：批量 72 条入库、`speed=250` 返回 422（`loc: ["body","speed"]`）、按设备查询与分组统计数字正确、自检通过、退出码 0
- [ ] `pytest -q` 全部通过（7 用例，离线、不依赖网络）；`ruff check .` 零告警
- [ ] `POST /telemetry` 传 `speed=250`/`soc=101`/负数返回 422 且错误是结构化 JSON（`detail[0].loc/type`）
- [ ] `GET /telemetry/stats` 不传设备 ID 时按设备分组返回（与 ph09 分组统计思维一致），传 `device_id` 时只统计该设备
- [ ] 数据库文件与日志产物只出现在系统临时目录（`tempfile.mkdtemp`），运行后 `git status` 工作区干净
- [ ] 能说清：依赖注入 `yield` Session 为什么能防连接池泄漏（主文档 4.4）；校验失败为什么自动 422 且不用手写 if（主文档 3.3）

## 扩展方向（可选）

- 给上报接口加 JWT 鉴权（`Depends(get_current_user)` 保护 `POST /telemetry`）——复用练习 2「登录注册」的 sol-02 代码
- 用 Alembic 迁移代替 `create_all`：`alembic init` + `autogenerate` 管理表结构（主文档 3.7），为 ph11 的库表演进打底
- 统计接口加时间桶聚合（按天/小时分组，SQLite 的 `strftime` + `GROUP BY`）——向 ph11 数据库阶段的时间序列查询过渡
- 批量上报改用异步 `async_sessionmaker` + `aiosqlite`，配合 ph14 并发阶段的高频采集场景
- 部署形态：uvicorn 起服务 + Nginx 反代 + Docker 打包——ph16 部署与 DevOps 阶段

## 验证环境

- Python 3.13.9；依赖：fastapi 0.139.1、uvicorn 0.50.0、sqlalchemy 2.0.43、pydantic 2.12.4（测试：pytest 8.4.2、httpx 0.28.1、ruff 0.12.0）
- 安装：`pip install fastapi uvicorn sqlalchemy pydantic pytest httpx ruff`（建议先在 venv 中安装，见 ph07）
- 运行 / 测试命令见「验收标准」各条
- 验证状态：已验证（`--demo` 离线链路退出码 0、pytest 7 用例全过、ruff 零告警，均在本环境实际执行通过）

`--demo` 实测输出（节选，数据库在临时目录）：

```text
批量上报 -> 201 {'inserted': 72} （3 台设备 × 24 条 = 72 条）
非法上报（speed=250）-> 422 ['body', 'speed'] less_than_equal
按设备查询 V001 前 3 条 -> 200 条数: 3 首条 speed: 55.0
全量分组统计:
   {'device_id': 'V001', 'count': 24, 'avg_speed': 60.75, 'max_speed': 67.0, 'avg_soc': 85.7}
   {'device_id': 'V002', 'count': 24, 'avg_speed': 67.75, 'max_speed': 74.0, 'avg_soc': 85.7}
   {'device_id': 'V003', 'count': 24, 'avg_speed': 74.75, 'max_speed': 81.0, 'avg_soc': 85.7}
单设备统计 V001      -> [{'device_id': 'V001', 'count': 24, 'avg_speed': 60.75, 'max_speed': 67.0, 'avg_soc': 85.7}]

自检通过：批量 72 条入库、非法上报 422、查询与统计结果正确
```
