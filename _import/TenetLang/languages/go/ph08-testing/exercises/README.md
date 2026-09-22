# ph08 测试与工程质量阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），建议按 1 → 2 → 3 → 4 顺序完成。四题与 roadmap 本阶段「练习」小节一一对应。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-table-test && go test -v`）。请勿在 exercises/ 根目录执行 `go test ./...`——根目录没有 go.mod。

## 练习 1：给业务函数写表格驱动测试（★）

**目标**：为中位数函数 `Median(values []float64) (float64, error)` 写一套表格驱动测试。

**要求**：

- 函数语义：空输入返回错误；偶数个元素取中间两数的平均值；**不得修改入参切片的元素顺序**
- 测试用「匿名结构体切片 + for 循环 + t.Run 子测试」组织，表结构包含 name / in / want / wantErr 四个字段
- 至少覆盖：空输入、单元素、奇数个、偶数个（需算平均）、含负数、入参顺序不被改变（测完后检查原切片）
- 浮点比较允许用「差的绝对值 < 1e-9」判定

**验收**：`go test -v` 全部子测试通过；`go test -cover` 覆盖率 100%（参考实现不含 main 入口，统计的正是 Median 全部语句；若你的实现带 main 演示代码，请改用 `go tool cover -func` 单独看 Median 的覆盖率）；`go vet ./...` 零报告。

## 练习 2：给 handler 写测试（★★）

**目标**：用 httptest 给一个设备查询 handler 写测试，不起端口、不碰网络。

**要求**：

- handler 写成工厂函数 `NewHandler(devices map[string]Device) http.Handler`，数据源注入而非全局变量
- 路由 `GET /devices/{id}`：存在返回 200 + JSON，不存在返回 404 + `{"error": ...}` JSON
- 测试覆盖三条路径：200（断言状态码 + 解析 JSON 字段）、404（断言状态码 + error 字段非空）、POST 同路径返回 405
- 断言失败信息要带上实际值与期望值

**验收**：`go test -v` 三条路径全部通过；`go vet ./...` 零报告。

## 练习 3：给并发代码跑 race（★★）

**目标**：找出并修复下面这段代码的数据竞争，用 race detector 验证修复有效。

```go
// 有竞争的计数器（题目给定的起点代码，故意有 bug）
type Counter struct{ n int }

func (c *Counter) Inc()        { c.n++ }
func (c *Counter) Value() int { return c.n }
```

**要求**：

- 先写一个并发测试：100 个 goroutine 各调用一次 `Inc()`，用 `sync.WaitGroup` 等待全部完成
- 用 `go test -race` 复现 DATA RACE，看懂报告中的两处 goroutine 栈
- 用 `sync.Mutex`（或 `sync/atomic`）修复，**不允许**用「串行化测试」来回避问题
- 修复后再跑 `go test -race ./...` 必须干净通过，且最终 `Value()` 等于 100

**验收**：`go test -race -v` 通过且无 DATA RACE 输出；`go vet ./...` 零报告。

## 练习 4：给核心模块写 benchmark（★★★）

**目标**：对比两种字符串拼接实现的性能，写出带 benchmem 结论的 benchmark。

**要求**：

- 实现两个函数：`ConcatPlus(parts []string) string`（用 `+=` 循环拼接）与 `ConcatBuilder(parts []string) string`（用 `strings.Builder`）
- 先写正确性测试：两种实现结果一致，且与 `strings.Join(parts, "")` 一致
- 再写两个 benchmark：100 个元素的切片，输出 ns/op、B/op、allocs/op
- benchmark 结果必须赋值给包级变量，防止被编译器优化消除
- 在 README 或注释里用一句话记录结论（哪个快、为什么）

**验收**：`go test` 正确性测试通过；`go test -bench=. -benchmem -run=^$` 两个 benchmark 均有输出；能口头解释 allocs/op 差异的来源；`go vet ./...` 零报告。

---

四个练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
