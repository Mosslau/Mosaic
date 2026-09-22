# ph13 性能优化 练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★）。四题与 roadmap ph13「练习」小节一一对应：优化 JSON 解析 / 分析高并发接口 / 查 goroutine 泄漏 / 优化锁竞争。
> 全部参考实现已在 go1.25.6（darwin/arm64）验证（`go test`、`go vet`、`go test -race` 全绿），零第三方依赖，进入各自子目录运行。

## 练习 1：优化 JSON 解析（★★）

**目标**：同一批 JSON 日志行，用 `map[string]any` 与具名 struct 各解析一遍，benchmark 量化 ns/op、B/op、allocs/op 差异，体会「减少分配次数」对 GC 压力的意义。

**要求**：
- 解析 1000 行 `{"level":...,"msg":...,"latency_ms":...}` 形式的日志
- 朴素版用 `map[string]any` + `fmt.Sprint` 提取字段；优化版用具名 struct（`json` tag）+ 结果 slice 预分配
- 两版输出必须一致（含坏行跳过行为一致）

**验收**：`go test -v ./...` 通过；`go test -run='^$' -bench=. -benchmem -benchtime=2000x` 输出两版三列指标，能解释每列差异来源（参考实现实测：struct 版快约 1.6 倍、allocs 20910→8009）

**提示**：sol-01 目录；注意 JSON 数字进 map 一律是 `float64`，取 latency 要类型断言

## 练习 2：分析高并发接口（★★★）

**目标**：对一个返回设备状态 JSON 的 HTTP handler，走完整流程——先 profile 定位热点，再优化，再基准验证；理解「连同测试桩一起基准会被桩的分配淹没」的度量陷阱。

**要求**：
- 朴素版用 `fmt.Fprintf` 拼响应体；优化版用 `sync.Pool` 复用 `bytes.Buffer` + `strconv.AppendInt` 免装箱
- 用 `runtime/pprof` 采集 CPU profile，`go tool pprof -top` 看热点在不在 `fmt` 路径
- 基准应直接测热点函数（`writeBody*`），而不是整 handler

**验收**：`go test -v ./...`、`go test -race ./...` 通过；benchmark 显示优化版更快并解释原因（参考实现实测：热点函数快约 2~3 倍；整 handler 差异被测试桩稀释到约 7%）

**提示**：sol-02 目录；`sync.Pool` 三要素 Get → Reset → Put，Reset 漏了会串数据

## 练习 3：查 goroutine 泄漏（★★）

**目标**：构造一个「调用方超时放弃后发送方永久阻塞」的泄漏场景，用 `runtime.NumGoroutine` 计数与 goroutine profile 定位泄漏点，再用缓冲 channel 修复。

**要求**：
- 泄漏版：n 个发送 goroutine 写无缓冲 channel，调用方只消费一半就返回——剩下 n/2 个发送方泄漏
- 修复版：缓冲容量 = 发送方数量，调用方放弃也不泄漏
- 用 goroutine profile（`pprof.Lookup("goroutine").WriteTo(&buf, 1)`）证明泄漏栈聚在哪个函数哪一行

**验收**：`go test -v ./...` 通过（泄漏版 goroutine 数增长、修复版不增长）；`go test -race ./...` 通过

**提示**：sol-03 目录；goroutine profile 的文本 dump 里能看到按调用栈聚合的泄漏 goroutine 数量

## 练习 4：优化锁竞争（★★★）

**目标**：同一个 string→int 缓存用「全局互斥锁」与「16 分片锁」两种策略实现，并发基准量化差异；理解分片摊薄竞争的原理与基准设计的坑。

**要求**：
- 两种缓存 API 一致（`Get`/`Set`），并发下结果正确、`-race` 无数据竞争
- 基准用 `RunParallel` + `-cpu=8` 放大竞争；key 必须预生成、洗牌、每 worker 错位起点——否则所有 worker 同步轮询同一 key 序列，竞争会集中在同一个分片上（实测那样设计分片反而更慢）
- 分片散列要均匀（验证 1000 个 key 覆盖 ≥14/16 片）

**验收**：`go test -v ./...`、`go test -race ./...` 通过；`-benchtime=1s -cpu=8` 下分片版快于全局锁版并解释原因（参考实现实测：快约 1.7 倍）

**提示**：sol-04 目录；分片是「以空间换竞争」——每片一把锁，竞争概率降为 1/16；先想清楚「锁是不是瓶颈」再动手（block/mutex profile 见示例 ex05）
