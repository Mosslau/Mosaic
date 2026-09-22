# examples —— Web 后端开发阶段完整示例

验证环境：go1.25.6（darwin/arm64），**仅标准库**（net/http、encoding/json、html/template、log/slog、crypto/hmac），无第三方依赖。模块声明 `go 1.22`（依赖 ServeMux 方法路由，需 Go 1.22+）。

运行方式：六个示例各自是**独立的 Go module**（目录内自带 go.mod），请先进入示例目录再运行——请勿在 examples/ 根目录执行 `go test ./...`（根目录没有 go.mod）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-routing/` | 路由与 JSON API：ServeMux 方法路由 + 通配符 `{id}` + PathValue + query 过滤 + 统一错误，覆盖 200/201/204/400/404/405/409 | `cd ex01-routing && go test -v`；`go run .` 后 curl 冒烟 |
| `ex02-middleware/` | 中间件组合：日志（log/slog 结构化 + 状态码捕获）+ panic 恢复 + CORS + 窗口限流（滑动时间窗日志），洋葱模型 `func(http.Handler) http.Handler` | `cd ex02-middleware && go test -v`；`go run .` 后 `curl -s http://127.0.0.1:18080/ping` |
| `ex03-todo-api/` | Todo API：五方法 CRUD + 内存切片存储（Mutex）+ 手写校验 + 统一错误，handler 四段式 | `cd ex03-todo-api && go test -v`；`go run .` 后 curl 冒烟 |
| `ex04-jwt-auth/` | JWT 认证：标准库手写 HS256 签发/验签（header.payload.signature + HMAC）+ 登录接口 + 鉴权中间件 | `cd ex04-jwt-auth && go test -v`；`go run .` 后 curl 冒烟 |
| `ex05-template-static/` | 模板 + 静态文件：html/template 渲染设备页（自动转义防 XSS）+ 表单 POST（PRG 303）+ http.FileServer | `cd ex05-template-static && go test -v`；`go run .` 后浏览器访问 http://127.0.0.1:18080/devices |
| `ex06-graceful-shutdown/` | 优雅关闭：http.Server 显式超时（ReadHeader/Read/Write/Idle）+ 信号监听 + srv.Shutdown(ctx) | `cd ex06-graceful-shutdown && go test -v`；冒烟脚本见 main.go 头部注释 |

## 实测数据（本环境跑出，如实记录）

全部示例通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go test ./...`（行为符合预期）；覆盖率与 benchmark 为本机实际输出：

| 示例 | go test -cover | 备注 |
|------|----------------|------|
| ex01-routing | 92.1% | 14 个用例全过（TestRoutes 12 个子用例 + 2 个专项断言，含 405 + Allow 头） |
| ex02-middleware | 89.7% | 6 个用例全过（CORS/恢复/限流/链顺序） |
| ex03-todo-api | 84.1% | 4 个用例全过；`go test -race` 并发用例干净通过 |
| ex04-jwt-auth | 82.4% | 10 个用例全过（签发/验签/篡改/过期/鉴权） |
| ex05-template-static | 79.5% | 5 个用例全过（含 XSS 转义断言） |
| ex06-graceful-shutdown | 21.1% | 单元测试只覆盖 handler 与超时配置；信号流程用冒烟测试验证（见下） |

ex04 JWT 签发 benchmark（`go test -bench=. -benchmem -run=^$ -benchtime=2000x`）：

```
BenchmarkSignJWT-14    	    2000	      1299 ns/op	    2236 B/op	      33 allocs/op
```

结论：一次 JWT 签发约 1.3μs、分配 33 次——对登录这种低频操作完全可忽略；教学价值在于理解 base64 + HMAC + JSON 三者的开销构成（生产用 golang-jwt 库，行为一致）。注：ns/op 与 B/op 随机器负载有约 ±10% 波动，allocs/op 稳定，上表为某次实测、仅量级参考。

ex06 冒烟测试（本地端口 18081，验证后进程已 kill、无残留）：

```
curl http://127.0.0.1:18081/healthz → ok
kill -TERM <pid> →
  收到退出信号，开始优雅关闭…
  所有连接已处理完毕，服务退出
退出码 0
```

## 注意事项

- 启动类示例（ex01/ex02/ex03/ex04/ex05）监听 `127.0.0.1:18080`，ex06 监听 `127.0.0.1:18081`——高位端口避开常见服务占用；用完 Ctrl-C / kill 干净，勿残留进程。
- `ex04-jwt-auth` 的 JWT 是**标准库手写教学实现**：完整实现 RFC 7519 的 HS256 流程（结构、验签、过期校验），可运行、可测试；生产环境建议换用 `github.com/golang-jwt/jwt/v5`（第三方模块，本环境未拉取验证）。
- 限流（ex02）为单机窗口限流（滑动时间窗日志：按时间戳剪枝计数）实现，只够学习；分布式限流（Redis 令牌桶）见 ph10 数据库阶段。
- 六个示例的验证状态均为：已验证（go1.25.6）。
