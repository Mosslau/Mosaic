# exercises —— 方法与接口阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），建议按 1 → 2 → 3 → 4 顺序完成。

运行方式：每个参考实现是独立的 `package main` 文件，用单文件模式运行 `go run sol-0X-xxx.go`（请勿在本目录执行 `go build ./...`，同一目录多个 `main` 会冲突）。

## 练习 1：Sensor 接口（★）

**目标**：定义只有一个方法的 `Sensor` 接口（`Read() float64`），写两个传感器实现，通过接口统一采集 3 轮。

**要求**：
- 一个实现用**值接收者**、另一个用**指针接收者**（指针接收者需要有修改内部状态的方法，如校准偏移）
- 写一个 `collect(sensors []Sensor, rounds int)` 函数对接口编程，打印每轮读数
- 在代码注释中解释：为什么指针类型的传感器也能放进 `[]Sensor`

**验收**：`go run sol-01-sensor.go` 输出 3 轮 × 2 传感器的读数，行为符合预期。

## 练习 2：Storage 接口（★★）

**目标**：定义显式返回 `error` 的 `Storage` 接口（`Save` / `Load` / `Delete`），用 `MemStorage` 实现，再写一个依赖接口的 `TodoService`。

**要求**：
- `Load` 未命中时返回哨兵错误 `ErrNotFound`，调用方用 `errors.Is` 判断
- `MemStorage` 零值可用：`data` 为 nil 时 `Save` 惰性初始化 map
- `TodoService` 不感知具体存储实现，错误信息用 `%w` 携带上下文
- 最后用 `errors.Is` 验证 `Load("no-such-key")` 确实命中 `ErrNotFound`

**验收**：`go run sol-02-storage.go` 完整跑通 添加 → 读取 → 删除 → 未命中 四条路径，退出码为 0。

## 练习 3：Logger 接口（★）

**目标**：定义小接口 `Logger`（`Log(level, msg string)`），实现 `ConsoleLogger` 与 `NilLogger`，通过依赖注入切换。

**要求**：
- `ConsoleLogger` 打印 `[level] msg`，`NilLogger` 什么都不做（no-op）
- 写一个业务类型（如 `DeviceService`）通过字段持有 `Logger`，初始化时注入
- 分别注入两种实现并调用业务方法，验证输出差异

**验收**：`go run sol-03-logger.go` 注入 `ConsoleLogger` 时打印日志、注入 `NilLogger` 时无输出。

## 练习 4：用接口模拟 BUS/UART 数据读取（★★★）

**目标**：用接口组合模拟一条完整的数据采集链路：`Reader` 接口 + 两个链路实现 + 采集器统计。

**要求**：
- 定义消费侧的 `Reader` 接口（`Read() (Frame, error)`），`Frame` 含来源与数值字段
- `BUSReader` / `UARTReader` 各自模拟连续读取，读到一定帧数后返回哨兵错误 `ErrLinkDown`（模拟链路中断）
- 采集器 `collect(r Reader)` 循环读取，遇到错误用 `errors.Is` 判断后正常结束并返回统计（帧数、均值），**不 panic**
- main 中同时驱动两路采集并打印各自统计

**验收**：`go run sol-04-can-uart.go` 输出两路的帧数与均值，链路中断处打印提示并正常退出（exit 0）。

---

四个练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
