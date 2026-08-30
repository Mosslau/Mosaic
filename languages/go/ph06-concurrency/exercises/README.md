# ph06 并发编程阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），建议按 1 → 2 → 3 → 4 顺序完成。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-worker-pool && go run .`）。请勿在 exercises/ 根目录执行 `go build ./...`——根目录没有 go.mod。

## 练习 1：worker pool（★★）

**目标**：固定 4 个 worker 并发处理 20 个「求平方」任务，汇总结果并安全关闭所有 channel。

**要求**：
- 输入任务 1..20，每个 worker 从任务 channel 取一个数，输出 `(任务号, 平方, worker 编号)`
- 发送方（main）负责 `close(jobs)`；worker 用 `range jobs` 消费并自动退出
- 用 WaitGroup 等全部 worker 退出后再关闭结果 channel，main 用 `range results` 汇总
- 最后打印 1² + 2² + … + 20² 的总和

**验收**：输出 20 条处理记录（含 worker 编号），总和 = 2870；程序正常退出——出现 `all goroutines are asleep - deadlock!` 即失败。

## 练习 2：并发爬虫（★★★）

**目标**：实现并发抓取：给定 URL 列表，固定 worker 并发抓取，每条带超时，fan-in 汇总成功与失败。

**要求**：
- 抓取用假 fetcher 模拟网络延迟（`time.Sleep` 后返回标题），不真正发网络请求——net/http 属 ph07 标准库阶段
- worker pool 扇出抓取（每个 URL 一条任务），结果经 channel 扇入汇总
- 每个请求带超时（用 `context.WithTimeout` 派生请求级 context）
- 超时/失败的 URL 计入失败列表并打印原因，不能卡死程序
- 建议：8 个 URL，其中 2 个故意慢于超时阈值

**验收**：输出 6 个成功标题 + 2 个失败原因与汇总统计；`go run -race .` 无 DATA RACE、无泄漏 goroutine。

## 练习 3：任务超时控制（★★★）

**目标**：对一组耗时不同的任务统一做超时控制：超时未完成则放弃并降级。

**要求**：
- 任务模拟耗时（如 300ms / 900ms / 1800ms），逐个执行
- 每个任务用 `context.WithTimeout`（如 1s）派生独立超时 context，任务函数检查 `ctx.Done()`
- 用 select 同时等待「任务完成」与「超时」，超时到达返回降级结果（如返回缓存/默认值）
- 任务 goroutine 与调用方都要有明确退出路径（注意：结果 channel 用缓冲，防止调用方放弃后发送方永久阻塞）

**验收**：短/中耗时任务成功返回结果，长耗时任务（1800ms）超时降级；程序在约 2s 内结束并打印三类任务的汇总。

## 练习 4：数据采集并发处理（★★★）

**目标**：模拟多设备并发上报采样，经 channel 汇聚到唯一聚合者去重/聚合，`-race` 验证无竞争。

**要求**：
- 每设备一个 goroutine 连续上报 10 条采样（设备 ID + 序号 + 数值），其中序号 3 的采样重复上报一次
- 采样经 channel 发给唯一的聚合 goroutine（用「单一消费者」避免共享 map 加锁）
- 聚合：按 (设备, 序号) 去重后，统计每台设备的有效样本数与总和/平均值
- 用 WaitGroup 等所有采集 goroutine 结束并关闭 channel，聚合完成后输出统计

**验收**：5 台设备共 50 条有效样本（重复上报被去重）；`go run -race .` 无 DATA RACE，输出每台设备统计与合计。

---

四个练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
