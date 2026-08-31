# ph08 阶段项目：带测试的设备管理 HTTP API

> 对应 Roadmap「测试与工程质量阶段」推荐项目。用测试驱动的方式搭一个可运行的 HTTP API，
> 把本阶段的核心技能全部用上：表格驱动测试、接口注入 mock、race detector、覆盖率、benchmark。

## 需求

一个设备管理 HTTP API：支持列出、查询、创建、删除设备。存储层是并发安全的内存实现
（`RWMutex` 保护），API 层通过 `Store` 接口依赖注入——这正是 ph08「接口有助于隔离测试依赖」必会概念的落地。

## 功能清单

- [x] `GET /devices` 列出全部设备（JSON）
- [x] `GET /devices/{id}` 按 ID 查询，不存在返回 404
- [x] `POST /devices` 创建设备，重复 ID 返回 409
- [x] `DELETE /devices/{id}` 删除设备，不存在返回 404
- [x] 存储层并发安全（`RWMutex`），`go test -race` 通过
- [x] handler 测试用 stub Store 隔离（不依赖真实存储）
- [x] 表格驱动测试 + 覆盖率统计 + benchmark（`store.go` 自带）

## 验收标准

- `go test -race ./...` 全部通过、`go vet ./...` 无告警
- `go test -cover ./internal/...` 覆盖率 ≥ 80%
- `go run ./cmd/api` 启动后：
  - `curl -s localhost:8080/devices` 返回 `[]`
  - `curl -s -X POST localhost:8080/devices -d '{"id":"d-001","status":"online"}'` 返回 201 与设备 JSON
  - 重复 POST 同一 ID 返回 409
  - `curl -s localhost:8080/devices/d-001` 返回该设备；`/devices/nope` 返回 404

## 扩展方向（可选）

- 持久化：把 `Store` 换成文件/数据库实现（属于 ph10 数据库阶段）
- 优雅关闭与超时控制（属于 ph09 Web 后端阶段）
- 为 `POST /devices` 增加校验：空 ID / 非法 status 返回 400（handler_test 补用例）

## 验证环境

go1.25.6（darwin/arm64），module 声明 `go 1.22`（ServeMux 方法路由需 Go 1.22+）。
构建：`go build ./...`；测试：`go test -race ./...`；运行：`go run ./cmd/api`。
已在本环境验证：`go test -race ./...` 通过、`go vet ./...` 零告警、覆盖率 80%+、API 冒烟测试符合验收标准。
