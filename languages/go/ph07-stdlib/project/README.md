# ph07 阶段项目：HTTP health check 工具

对应 roadmap ph07 推荐项目第一个「HTTP health check 工具」：给定一组 URL，周期性并发发起 GET 请求，统计状态码/延迟/失败率，超时可控，结果输出表格——net/http 客户端 + time + flag + context 的标准库组合落地。

## 需求

- `internal/checker` 探测核心：
  - `Check(ctx, client, url)` —— 单 URL 探测：请求级 context 超时、计时、返回状态码/延迟/错误
  - `CheckAll(ctx, client, urls, timeout)` —— 并发探测全部 URL（每个请求独立超时），汇总为 `Report`（总数/健康数/失败数/失败率），结果按 URL 排序保证输出稳定
  - `Result.OK()` —— 健康判定：2xx/3xx 且无错误视为健康
- `cmd/healthcheck` 命令行入口：
  - `-urls`（必填，逗号分隔）、`-interval`（探测间隔）、`-timeout`（单请求超时）、`-once`（单轮模式，供脚本与自测）
  - 周期性探测并打印表格报告；Ctrl+C 经 `signal.NotifyContext` 优雅退出

## 功能清单

| 功能 | 说明 |
|------|------|
| 并发探测 | 每 URL 一个 goroutine，各写各的结果槽位，无共享写冲突 |
| 超时控制 | 请求级 `context.WithTimeout` + 客户端兜底超时 |
| 健康判定 | 2xx/3xx 健康；网络错误、超时、5xx 计入失败 |
| 统计汇总 | 总数/健康/失败/失败率，结果按 URL 排序 |
| 表格输出 | URL、状态码、延迟、错误四列 |
| 优雅退出 | signal.NotifyContext 捕获 Ctrl+C |
| 单元测试 | httptest 模拟快/慢/失败/不可达端点，覆盖统计口径与超时语义 |

## 验收标准

- [ ] `gofmt -l .` 零差异、`go vet ./...` 零报告、`go build ./...` 通过
- [ ] `go test -v ./...` 全部通过（快/慢/失败/不可达四类端点的统计口径、超时控制、OK 判定表驱动用例）
- [ ] `go run ./cmd/healthcheck -urls "http://127.0.0.1:1/down" -timeout 300ms -once` 输出失败率 100% 的表格
- [ ] 缺 `-urls` 时打印用法并以非零状态退出
- [ ] 代码符合 ph07 要点：显式 error 返回、context 贯穿 I/O、net/http 惯用模式、无 panic

## 扩展方向

- 结果输出 JSON（`-format json`，复用 Report 的 json tag）
- 历史趋势：多轮结果落盘，输出延迟 p50/p95（ph08 可用 benchmark 压测探测开销）
- 失败告警：连续 N 轮失败后回调 webhook（ph09 Web 框架阶段可做成服务）
- 探测目标从配置文件读取（练习 2 的 JSON 配置解析器可直接复用）
- HTTP method/header/期望状态码可配置（如探活 POST 接口）

## 验证环境

- Go 1.22.2（darwin/arm64），无第三方依赖
- 运行命令：
  - `go run ./cmd/healthcheck -urls "<URL 列表>" -interval 5s -timeout 2s`
  - `go run ./cmd/healthcheck -urls "<URL>" -once`（单轮自测）
  - `go test -v ./...`
  - `go build ./...`
- 验证状态：已验证（Go 1.22.2）
