# ph09 阶段项目：设备数据上报 API

> 对应 Roadmap「Web 后端开发阶段」推荐项目。把本阶段的技能拼成一个完整服务：
> **JWT 设备认证（examples/ex04）+ 参数校验与统一错误（examples/ex03）+ 限流中间件（examples/ex02）+ 优雅关闭（examples/ex06）**，
> 数据暂存内存 map（ph10 换数据库）。

## 需求

设备端定时向服务上报位置 / 速度 / 状态。接口含：

- **鉴权（设备 token）**：设备用预置密钥换 JWT（HS256，24h 有效），上报接口要求 `Authorization: Bearer <token>`，且 token 归属的设备必须与路径一致（设备只能上报自己的数据）
- **参数校验**：速度范围（0~300 km/h）、坐标合法（lat ∈ [-90,90]、lng ∈ [-180,180]）
- **限流（每设备每分钟 N 次）**：窗口限流器（滑动时间窗日志），超限 429
- **统一错误码**：全部错误走 `{code, message}`（UNAUTHORIZED / FORBIDDEN / RATE_LIMITED / INVALID_PARAM / NOT_FOUND / INVALID_JSON）
- 数据暂存内存 map（RWMutex 保护），ph10 换真实数据库

## 目录结构

```text
project/
├── cmd/api/main.go            # 入口：预置数据 + 组装 + http.Server 超时 + 信号优雅关闭
└── internal/
    ├── auth/                  # JWT 手写签发/验签（Sign/Verify）+ 鉴权中间件（Middleware）
    ├── device/               # 内存设备存储（Store 接口 + RWMutex 实现）
    └── api/                   # 路由 + 各接口 + 每设备限流器（deviceLimiter）
```

## 接口一览

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/healthz` | 无 | 健康检查 |
| POST | `/api/devices/auth` | 无 | `{device_id, secret}` → `{token}`（设备认证换 JWT） |
| GET | `/api/devices` | 无 | 列表，`?status=online\|offline` 过滤，非法值 400 |
| GET | `/api/devices/{id}` | 无 | 详情，不存在 404 |
| POST | `/api/devices/{id}/report` | Bearer JWT | 上报 `{speed, lat, lng}`；校验失败 400、超限 429、归属不符 403 |

## 功能清单

- [x] 设备认证：预置密钥换 JWT（24h 有效），错误密钥 401
- [x] 上报接口：JWT 鉴权 + 归属校验（token 设备 == 路径设备）+ 速度/坐标校验 + 限流
- [x] 列表 / 详情只读接口（无鉴权，产品可自行加策略）
- [x] 每设备窗口限流（滑动时间窗日志，默认每设备每分钟 10 次，可配置）
- [x] 统一错误结构 `{code, message}`
- [x] 内存存储并发安全（RWMutex），`go test -race ./...` 通过
- [x] http.Server 显式超时 + SIGINT/SIGTERM 优雅关闭（实测退出码 0）

## 验收标准

- `go test ./...` 全部通过、`go vet ./...` 零告警、`go test -race ./...` 无数据竞争
- `go test -cover ./...` 覆盖率：internal/api 83.9%、internal/auth 57.7%、internal/device 100.0%（实测，go1.25.6）
- `go run ./cmd/api` 启动后（127.0.0.1:18080）：
  - `curl -s http://127.0.0.1:18080/healthz` 返回 `ok`
  - `POST /api/devices/auth`（`{"device_id":"car-001","secret":"sec-car-001"}`）返回 token
  - 带 token 上报 `/api/devices/car-001/report` 返回 200 与更新后的设备 JSON；不带 token 返回 401
  - 上报速度 301 返回 400；每分钟第 11 次上报返回 429
  - `curl -s http://127.0.0.1:18080/api/devices` 返回三台设备 JSON
- 上述冒烟测试已在本环境实测通过（go1.25.6，darwin/arm64），服务测完已 kill，无残留进程

## 扩展方向（可选）

- **持久化**：把 `device.Store` 换成 MySQL/Redis 实现，设备注册与状态落库（ph10 数据库阶段）
- **分布式限流**：单机 map 限流换成 Redis 令牌桶（`golang.org/x/time/rate` + go-redis，ph10）
- **设备注册**：预置密钥改为注册流程 + 密码哈希存储（bcrypt）
- **API 文档**：为全部接口补 OpenAPI 描述（swaggo 等第三方，本阶段未引入）
- **观测**：接入 log/slog 结构化日志 + 指标（Prometheus 属 ph12 云原生与部署阶段）

## 验证环境

go1.25.6（darwin/arm64），module 声明 `go 1.22`（ServeMux 方法路由需 Go 1.22+）。**仅标准库**，无第三方依赖。
构建：`go build ./...`；测试：`go test ./...` / `go test -race ./...` / `go test -cover ./...`；运行：`go run ./cmd/api`。
已在本环境验证：go vet 零报告、全部测试通过（含 -race）、覆盖率如上、HTTP 冒烟测试符合验收标准、优雅关闭退出码 0。
