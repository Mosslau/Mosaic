# ph03 阶段项目：设备状态管理 CLI

对应 Roadmap「ph03 Slice、Map、Struct 阶段」推荐项目之一。实现一个设备状态管理 CLI：用 map + struct 管理设备列表、查询单设备状态、更新资源指标、按状态筛选。

## 需求

一个命令行演示程序，覆盖 Slice、Map、Struct 三大数据原语：

- 内置一批设备种子数据（`map[string]Device`），设备是 `Device` struct（ID、Type、Status、CPU、Mem）
- 支持子命令：`list`（列全部）、`show`（查单个）、`update`（更新指标）、`filter`（按状态筛选）、`summary`（统计）
- 更新设备时体现「struct 是值类型、需回写」这一核心陷阱
- 遍历输出用 Slice 收集 key 后 `sort`，保证输出顺序稳定（map 遍历无序）

## 功能清单

- [ ] `list`：按 ID 升序列出全部设备
- [ ] `show <id>`：用 ok 模式查询单个设备，不存在给提示
- [ ] `update <id> [-cpu 值] [-mem 值] [-status 值]`：更新并回写，id 不存在返回错误
- [ ] `filter <status>`：按状态筛选，返回 `[]Device` 且按 ID 有序
- [ ] `summary`：统计在线/离线数量与所有设备平均 CPU/Mem

## 验收标准

- `go run main.go device.go list` 按 ID 升序输出 5 台种子设备
- `go run main.go device.go show cam-002` 输出其 offline 状态与零指标
- `go run main.go device.go update cam-002 -cpu 23.7 -status online` 输出「更新后 Status=online CPU=23.7%」（更新后立即回查，验证 struct 回写生效）
- `go run main.go device.go filter online` 只列出 Status 为 online 的设备
- `go run main.go device.go summary` 输出总计/在线/离线与平均资源利用率
- 全程序不使用 `panic` 处理业务逻辑；所有错误经显式 `error` 返回

## 扩展方向（可选）

- 设备列表持久化到文件（读写 JSON/CSV）—— 属于 ph07 标准库阶段
- 为管理函数写表驱动单元测试 —— 属于 ph08 测试阶段
- 给 `update` 加并发安全（多 goroutine 操作 map）—— 属于 ph06 并发阶段
- 用 interface 抽象「设备存储」以支持替换数据源 —— 属于 ph04 方法与接口阶段

## 验证环境

Go 1.22.2（darwin/arm64），无外部依赖（仅标准库）。本仓库无 go.mod，运行与静态检查需显式列出源文件。

```bash
# 1. 运行（project/ 目录下）
go run main.go device.go list
go run main.go device.go show cam-002
go run main.go device.go update cam-002 -cpu 23.7 -status online
go run main.go device.go filter online
go run main.go device.go summary

# 2. 静态检查
go vet main.go device.go
gofmt -l .
```

已在本环境验证：`gofmt -l` 无差异、`go vet` 通过、上述命令输出符合预期。
