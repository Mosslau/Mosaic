# ph10 阶段项目：设备轨迹存储服务

> 对应 Roadmap「数据库阶段」推荐项目之二（与 ph09 阶段项目「设备数据上报 API」一脉相承——ph09 数据暂存内存 map，本阶段落库）。把本阶段的技能拼成一个完整服务：
> **SQLite 持久化（批量事务写入 + 设备时间复合索引）+ Redis 最新位置旁路缓存（go-redis，故障降级内存缓存）+ HTTP 接口（ph09 的 handler 四段式与统一错误延续）+ 优雅关闭**。

## 需求

设备端端定时上报 GPS 点（device_id、lat、lng、speed、ts），服务把轨迹落库、按"设备 + 时间"建索引，Redis 缓存"最新位置"（短 TTL），提供三类接口：

- **批量上报**：一次上报一批 GPS 点，事务内全部写入（任一点非法整体回滚）
- **查最新位置**：走旁路缓存——先 Redis，未命中查库并回填
- **查时间段轨迹**：按 from/to 时间窗口返回升序轨迹

## 目录结构

```text
project/
├── cmd/api/main.go            # 入口：组装 Store+Cache+路由，http.Server 超时 + 优雅关闭
└── internal/
    ├── store/                 # SQLite 存储：devices/gps_points 表 + 复合索引，事务批量写入
    ├── cache/                 # 最新位置缓存：Cache 接口 + Redis 实现 + 内存实现（测试/降级）
    └── api/                   # HTTP 接口：上报/最新位置/轨迹 + 校验 + 统一错误 {code, message}
```

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/healthz` | 健康检查 |
| POST | `/api/devices/{id}/points` | 批量上报 `{"points":[{lat,lng,speed,ts}]}`；校验坐标/速度/时间，201 |
| GET | `/api/devices/{id}/latest` | 最新位置（旁路缓存）；无数据 404 |
| GET | `/api/devices/{id}/trajectory?from=...&to=...` | 时间段轨迹（RFC3339，升序）；参数非法 400 |

## 功能清单

- [x] 批量上报：事务写入（任一点失败整体回滚）+ 坐标/速度/时间校验（非法 400）
- [x] 最新位置：旁路缓存三件套（Redis 短 TTL 30s；Redis 故障自动降级内存缓存——缓存不致命）
- [x] 时间段轨迹：`(device_id, ts)` 复合索引 + 范围查询
- [x] 统一错误结构 `{code, message}`（INVALID_JSON / INVALID_PARAM / NOT_FOUND / INTERNAL）
- [x] handler 四段式（解析→校验→业务→响应），数据层只依赖 Store/Cache 接口
- [x] http.Server 显式超时 + SIGINT/SIGTERM 优雅关闭（实测退出码 0）

## 验收标准

- `go test ./...` 全部通过、`go vet ./...` 零告警、`go test -race ./...` 无数据竞争
- `go test -cover ./...` 覆盖率：internal/api 80.8%、internal/cache 84.0%、internal/store 78.3%（实测，go1.25.6；cache 的 84.0% 含 Redis 实测用例）
- `go run ./cmd/api -addr 127.0.0.1:18080` 启动后（本环境实测通过，测完已 kill、无残留进程与二进制）。注：**优雅关闭"退出码 0"需用编译产物验证**（`go build -o /tmp/device-api ./cmd/api && /tmp/device-api -addr 127.0.0.1:18080` 再 `kill -TERM`）——经 `go run` 包装启动时 SIGTERM 由 go run 转发给子进程，进程退出码为 143、优雅关闭日志不显示，这是 go run 的信号包装行为，非代码缺陷：

```text
GET  /healthz                                  → ok
POST /api/devices/car-001/points               → {"inserted":2}
GET  /api/devices/car-001/latest               → {"device_id":"car-001","lat":31.2,"lng":121.3,"speed":70,"ts":"2025-01-01T00:01:00Z"}
GET  /api/devices/car-001/trajectory?from=...  → 升序轨迹 JSON
POST 非法坐标（lat=91）                          → 400
GET  /api/devices/ghost/latest                 → 404
kill -TERM → "收到退出信号" → "所有连接已处理完毕，服务退出"，退出码 0
```

- 数据库驱动：**modernc.org/sqlite v1.57.0**（纯 Go 无 cgo），Redis 客户端 go-redis v9.22.0（127.0.0.1:16379，可选——不可达自动降级内存缓存，测试不依赖 Redis 也能全绿）

## 验证环境

go1.25.6（darwin/arm64），依赖：modernc.org/sqlite v1.57.0、github.com/redis/go-redis/v9 v9.22.0。依赖拉取：`GOPROXY=https://goproxy.cn,direct GOSUMDB=off GOCACHE=/tmp/gocache`（本机默认 proxy.golang.org 不可达，goproxy.cn 可达）。

```bash
# 1. 构建与测试
go build ./...
go test ./... && go test -race ./... && go vet ./...
# 2. 运行（Redis 可选；有 Redis 则缓存走 Redis，无则自动降级内存）
go run ./cmd/api -addr 127.0.0.1:18080
# 3. 冒烟（另开终端）
curl -s http://127.0.0.1:18080/healthz
curl -s -X POST http://127.0.0.1:18080/api/devices/car-001/points \
  -d '{"points":[{"lat":31.1,"lng":121.2,"speed":60,"ts":"2025-01-01T00:00:00Z"}]}'
curl -s http://127.0.0.1:18080/api/devices/car-001/latest
curl -s "http://127.0.0.1:18080/api/devices/car-001/trajectory?from=2025-01-01T00:00:00Z&to=2025-01-01T01:00:00Z"
# 4. 停止（优雅关闭）
kill -TERM <pid>
```

## 扩展方向（可选）

- **认证接入**：把 ph09 项目的手写 HS256 JWT 鉴权中间件挂到上报接口（token 归属设备 == 路径设备）
- **迁移管理**：用 golang-migrate/goose 把建表 SQL 改成版本化迁移文件（3.9 小节；本环境未安装 CLI，未验证）
- **Redis 分布式限流**：每设备每分钟 N 次上报，用 Redis INCR + TTL 实现（3.10/3.11 小节）
- **轨迹抽样**：超长时间段轨迹按时间抽稀（如每 5 分钟取一点），避免大数据量响应
- **微服务化**：把 store 拆成独立数据服务、走 gRPC 暴露查询——属 ph11 微服务与 RPC 阶段
