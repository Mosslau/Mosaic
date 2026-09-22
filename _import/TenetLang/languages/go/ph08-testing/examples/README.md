# examples —— 测试与工程质量阶段完整示例

验证环境：go1.25.6（darwin/arm64），仅标准库，无第三方依赖。

运行方式：六个示例各自是**独立的 Go module**（目录内自带 go.mod），请先进入示例目录再运行——请勿在 examples/ 根目录执行 `go test ./...`（根目录没有 go.mod）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-table-test/` | 表格驱动测试：表 + 循环 + t.Run 子测试，wantErr 字段覆盖错误路径 | `cd ex01-table-test && go test -v` |
| `ex02-http-test/` | httptest 测试 HTTP handler：工厂函数 + 依赖注入，断言状态码与 JSON，含 405 | `cd ex02-http-test && go test -v` |
| `ex03-race-detector/` | race 检测：`racy/` 故意无锁（-race 下预期报 DATA RACE），`fixed/` Mutex 修复版 | `cd ex03-race-detector && go test -race ./...` |
| `ex04-mock-stub/` | mock 隔离外部依赖：Reporter 接口 + 手写 stub，调用记录做行为断言 | `cd ex04-mock-stub && go test -v` |
| `ex05-benchmark-cover/` | benchmark + 覆盖率：json.Marshal vs 手写格式化，包级 sink 防优化消除 | `cd ex05-benchmark-cover && go test -bench=. -benchmem -run=^$` |
| `ex06-fuzz-test/` | fuzz testing + Example：不变量断言（对照 strings.Fields），Example 输出比对 | `cd ex06-fuzz-test && go test -v`，再 `go test -fuzz=FuzzWordCount -fuzztime=10s` |

注意事项：

- `ex03-race-detector/racy/` 是**故意出错示例**：`go test -race ./racy` 预期失败并输出 `WARNING: DATA RACE`——这正是要演示的效果；不加 `-race` 运行时该用例自动跳过（避免并发 map 写崩溃）。`fixed/` 包在 `-race` 下干净通过。
- 其余五个示例均已通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go test`（行为符合预期）；ex05 的 benchmark 与 ex06 的 10 秒 fuzz 也已实际运行。验证状态：已验证（go1.25.6）。
