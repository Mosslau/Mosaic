# Go 并发编程 Goroutine 与 Channel 阶段

> "不要通过共享内存来通信，而要通过通信来共享内存"——goroutine 与 channel 构成的并发模型，是后端服务、云原生、通用数据平台方向的核心能力。

## 1. 概述

Go 并发编程阶段的目标是：**掌握 goroutine 与 channel 构成的核心并发模型，以及 select、WaitGroup、Mutex、RWMutex、context 等同步与生命周期控制工具**。ph05 解决了"代码怎么组织"，本阶段回答"代码怎么跑得快"——从单线程顺序执行进入多任务并行执行，数据采集、任务调度、日志处理等后端核心场景全部依赖并发模型。

| 核心维度 | 覆盖内容 |
|----------|---------|
| goroutine | go 语句启动、轻量级并发单元、生命周期管理 |
| channel | 无缓冲/有缓冲、发送接收语义、关闭规则 |
| select | 多路复用、default 分支、time.After 超时 |
| 同步原语 | WaitGroup、Mutex、RWMutex |
| context | 取消与超时传播、WithCancel/WithTimeout/WithDeadline |
| 组合模式 | worker pool、fan-in、fan-out |
| 并发安全 | 数据竞争、race detector、channel vs mutex |

Go 的并发哲学是"语言层面内置并发"：`go` 是关键字、channel 是一等公民。但"goroutine 很便宜"不等于"不用管理"——**主动管理生命周期是本阶段最重要的心智转变**。

范围边界：承接 ph05 的多包工程化；不涉及标准库深入（ph07）、微服务与 RPC（ph11）、消息中间件（ph19）；GMP 调度与内存模型的实现细节点到即止。

## 2. 来源与演变

Go 的并发模型源自 **CSP（Communicating Sequential Processes，通信顺序进程）**——Tony Hoare 于 1978 年提出的理论：**不通过共享内存通信，而通过通信共享内存**。2007 年 Go 立项时，Rob Pike、Ken Thompson 等人选定 CSP 为并发核心：C/C++ 多线程复杂易错、Java 的 Thread 1:1 映射 OS 线程成本高——都不适合"让并发变得容易"的目标。

goroutine 的设计动机是**足够便宜的并发原语**——让开发者放心创建成千上万个并发任务。Go 1.1 引入 work stealing 调度与 race detector，Go 1.4 改为连续栈（栈起步降到 2KB），Go 1.5 将 GOMAXPROCS 默认设为 CPU 核数并重构调度器——"百万 goroutine"逐步成为现实。

| 时间 | 事件 |
|------|------|
| 1978 | Tony Hoare 提出 CSP 模型——Go 并发通信的理论基础 |
| 2007 | Go 立项，CSP 被选为并发核心（goroutine + channel） |
| 2009 | Go 开源，goroutine 与 channel 首次亮相 |
| 2012 | Go 1.0 发布，并发模型稳定 |
| 2013 | Go 1.1：引入 race detector（-race）与 work stealing 调度 |
| 2014 | Go 1.4：连续栈替代分段栈，goroutine 栈起步 2KB |
| 2015 | Go 1.5：GOMAXPROCS 默认 = CPU 核数，调度器重构 |
| 2020 | Go 1.14：基于信号的异步抢占，死循环 goroutine 不再饿死他人 |

**设计哲学**：并发是"语言特性"而非"库能力"——与 Java（靠 java.util.concurrent 库）、Python（受 GIL 限制）根本不同。

本文示例以 **Go 1.21+** 为基线（context 超时、`sync/atomic` 可用），验证工具链 Go 1.22.2 darwin/arm64。

## 3. 语法与参数

### 3.1 goroutine 与 go 语句

goroutine 是由 Go 运行时管理的**轻量级并发执行单元**，函数调用前加 `go` 关键字即异步启动：

```go
package main
import (
    "fmt"
    "time"
)
func main() {
    go fmt.Println("hello") // go 语句：异步启动，立即返回
    fmt.Println("world")    // 主 goroutine 继续执行
    time.Sleep(10 * time.Millisecond) // 等后台 goroutine 跑完
}
```

要点：**main 返回程序即退出**，未完成的 goroutine 被强制终止；goroutine 与 OS 线程是 M:N 关系（见 4.1），创建开销远小于线程。**坑**：**goroutine 泄漏**——永久阻塞在 channel 上，栈与引用对象无法回收，每个 goroutine 都要有明确退出路径；**主 goroutine 提前退出**——程序秒退、后台任务从未执行，必须用 WaitGroup 或 channel 等待。

### 3.2 channel 基础：无缓冲与有缓冲

channel 是内建通信原语，类型 `chan T`，`make` 创建、`<-` 收发：

```go
package main
import "fmt"
func main() {
    buffered := make(chan string, 2) // 有缓冲：容量 2，未满时发送不阻塞
    buffered <- "信号 A"
    buffered <- "信号 B"
    fmt.Println(<-buffered) // 取出 "信号 A"
    _ = make(chan int)      // 无缓冲：容量 0，收发必须配对
}
```

| 特性 | 无缓冲 channel | 有缓冲 channel |
|------|--------------|---------------|
| 创建 | `make(chan T)` | `make(chan T, n)` |
| 发送/接收 | 阻塞直到对方就绪（**同步配对**） | 缓冲未满/非空即返回（异步解耦） |
| 典型用途 | 信号传递、goroutine 间同步 | 任务队列、限流 |

**关闭规则（发送方负责关闭）**：向已关闭 channel 发送会 **panic**；重复关闭会 **panic**；接收方用 `v, ok := <-ch` 检测关闭（ok=false 表示已关闭取空）；`range ch` 自动在关闭取空后结束。**死锁**：所有 goroutine 都阻塞在 channel 上时，运行时 panic `all goroutines are asleep - deadlock!`。

### 3.3 select 多路复用

select 同时等待多个 channel 操作，类似 switch 但专用于 channel：

```go
package main
import (
    "fmt"
    "time"
)
func main() {
    ch := make(chan string)
    go func() { time.Sleep(10 * time.Millisecond); ch <- "数据" }()
    select {
    case msg := <-ch:
        fmt.Println("就绪:", msg)
    case <-time.After(200 * time.Millisecond):
        fmt.Println("超时：没有数据")
    }
}
```

要点：多个 case 同时就绪时**随机选择**（保证公平）；`default` 分支实现**非阻塞检查**；`time.After(d)` 返回 `<-chan time.Time`，是超时控制的惯用手段；`select {}` 永久阻塞，常用于 main 挂起等待后台 goroutine。

### 3.4 WaitGroup 等待组

`sync.WaitGroup` 等待一组 goroutine 完成：Add 增加、Done 减少、Wait 阻塞到归零：

```go
package main
import (
    "fmt"
    "sync"
)
func main() {
    var wg sync.WaitGroup
    for i := 1; i <= 3; i++ {
        wg.Add(1) // 必须在启动 goroutine 前调用
        go func(id int) {
            defer wg.Done() // defer 保证无论成败都减
            fmt.Printf("worker %d 完成\n", id)
        }(i)
    }
    wg.Wait()
    fmt.Println("全部完成")
}
```

**坑**：Add 与 Wait 不能并发（循环内 Add、循环后 Wait）；WaitGroup **不可复制**（传参必须用指针）；Done 多于 Add 会 panic；把 Add 放进 goroutine 内会导致 Wait 提前返回。

### 3.5 Mutex 与 RWMutex

roadmap 必会概念：**channel 用于通信，mutex 用于保护共享状态**。

```go
package main
import (
    "fmt"
    "sync"
)
type Counter struct {
    mu    sync.Mutex
    value int
}
func (c *Counter) Inc() { c.mu.Lock(); defer c.mu.Unlock(); c.value++ }
func (c *Counter) Value() int { c.mu.Lock(); defer c.mu.Unlock(); return c.value }
func main() {
    var wg sync.WaitGroup
    c := &Counter{}
    for i := 0; i < 1000; i++ {
        wg.Add(1)
        go func() { defer wg.Done(); c.Inc() }()
    }
    wg.Wait()
    fmt.Println("计数:", c.Value()) // 1000
}
```

`sync.RWMutex` 适合**读多写少**：`RLock`/`RUnlock` 读锁共享（多个读者并发），`Lock`/`Unlock` 写锁独占。**坑**：Mutex **不可复制**（复制后锁状态未定义——呼应 ph04 指针接收者规则）；锁必须配对，用 defer 保证；对同一把锁重复 Lock 会自身死锁。

### 3.6 context 取消与超时

roadmap 必会概念：**context 用于取消和超时传播**，沿调用链显式传递，向 goroutine 树广播取消信号：

```go
package main
import (
    "context"
    "fmt"
    "time"
)
func main() {
    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel() // 即使超时自动触发也要调用，释放资源
    go func() {
        <-ctx.Done() // 取消信号到达
        fmt.Println("worker 退出:", ctx.Err())
    }()
    time.Sleep(200 * time.Millisecond)
}
```

| 函数 | 用途 |
|------|------|
| `context.Background()` | 根 context，永不取消 |
| `WithCancel(parent)` | 手动取消，返回 cancel 函数 |
| `WithTimeout(parent, d)` / `WithDeadline(parent, t)` | 超时/截止时间自动取消 |
| `WithValue(parent, k, v)` | 携带请求级键值（不用于函数传参） |

要点：`ctx.Done()` 在取消时关闭；`ctx.Err()` 返回 `context.Canceled` 或 `context.DeadlineExceeded`；**cancel 必须调用**（`defer cancel()` 是铁律）；ctx 按惯例作为第一个参数、命名 `ctx`，不存进 struct。

### 3.7 worker pool 模式

worker pool（工作池）：固定数量 worker 从任务 channel 取任务，控制并发度、复用 goroutine：

```go
package main
import (
    "fmt"
    "sync"
)
func worker(id int, jobs <-chan int, wg *sync.WaitGroup) {
    defer wg.Done()
    for j := range jobs { // channel 关闭且取空后 range 自动结束
        fmt.Printf("worker %d 处理任务 %d\n", id, j)
    }
}
func main() {
    jobs := make(chan int, 5)
    var wg sync.WaitGroup
    for i := 1; i <= 3; i++ {
        wg.Add(1)
        go worker(i, jobs, &wg)
    }
    for j := 1; j <= 5; j++ { jobs <- j }
    close(jobs) // 发送方（main）负责关闭
    wg.Wait()
    fmt.Println("全部完成")
}
```

要点：关闭规则完整落地——**发送方关闭 jobs**，worker 用 range 消费并自动退出；worker 数量固定 = 并发度上限（完整版见示例 4）。

### 3.8 fan-in / fan-out

**fan-out（扇出）**：一个生产者分发任务到多个消费者（worker pool 即 fan-out）；**fan-in（扇入）**：多个输入汇聚到一个 channel：

```go
package main
import (
    "fmt"
    "sync"
)
func fanIn(chs ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    for _, ch := range chs {
        wg.Add(1)
        go func(c <-chan int) {
            defer wg.Done()
            for v := range c {
                out <- v
            }
        }(ch)
    }
    go func() { wg.Wait(); close(out) }() // 输入全部耗尽后关闭输出
    return out
}
func main() {
    a, b := make(chan int), make(chan int)
    go func() { for i := 1; i <= 3; i++ { a <- i }; close(a) }()
    go func() { for i := 10; i <= 12; i++ { b <- i }; close(b) }()
    for v := range fanIn(a, b) { fmt.Println(v) }
}
```

要点：fan-in 的关闭时机——**等所有输入 channel 关闭并消费完再关闭输出**（WaitGroup 收口）；fan-in/fan-out 组合可构建流水线：采集 → 清洗 → 聚合。

## 4. 底层原理

### 4.1 GMP 调度模型

goroutine 与线程是 **M:N 调度**——N 个 goroutine 映射到 M 个 OS 线程，由运行时负责调度。三要素：**G（Goroutine）** 是 goroutine 本身（含栈、状态）；**M（Machine）** 是 OS 线程，真正执行代码；**P（Processor）** 是逻辑处理器，持有本地运行队列，**GOMAXPROCS 即 P 的数量**（默认 = CPU 核数）。

调度循环：P 从本地队列取 G 执行 → G 阻塞（channel 操作、系统调用）时 M 与 P 解绑，P 换绑新 M 继续 → 本地队列空时从全局队列或其他 P **窃取（work stealing）** → G 唤醒后重新入队。关键推论：

- **G 阻塞不等于线程阻塞**：阻塞的 G 被挂起，M 转身执行其他 G——"百万 goroutine"可行性的根基
- **异步抢占（Go 1.14+）**：基于信号抢占长时间运行的 G，死循环不再饿死其他 goroutine

### 4.2 channel 的内存模型

channel 操作构成 **happens-before（先行发生）** 关系，是 Go 内存模型的核心保障——"通过通信共享内存"的底层就是这些同步屏障：

- 无缓冲 channel 的**发送 happens-before 对应接收完成**：接收方取到值后，一定能看到发送方之前的所有写入
- **channel 关闭 happens-before 接收方收到零值返回**：检测到关闭时能看到关闭前所有发送方的写入
- 有缓冲 channel：第 n 次接收 happens-after 第 n 次发送
- sync 原语同理：Mutex 的 Unlock happens-before 后续 Lock；WaitGroup 的 Done happens-before Wait 返回

**没有 happens-before 关系的并发读写就是数据竞争**——这正是 race detector 要抓的问题。

### 4.3 goroutine 栈与内存占用

- **栈起步 2KB**（Go 1.4 起），远小于 OS 线程默认栈（Linux 约 8MB）——百万 goroutine 的内存基础
- **连续栈、动态增长**：需要时复制到更大的新栈（倍增，上限 1GB），复制时重定位所有指针
- 对比 OS 线程：创建需内核介入、栈预留 8MB；goroutine 仅用户态分配，快几个数量级
- **goroutine 泄漏的本质**：泄漏的 goroutine 栈永远无法回收，其引用的对象也无法被 GC

### 4.4 数据竞争与 race detector 原理

**数据竞争（data race）**：多个 goroutine 并发访问同一内存位置、至少一个是写、且无 happens-before 关系——结果不可预测。`-race` 基于 ThreadSanitizer：

- **编译期插桩**：记录每个内存访问与 happens-before 关系（锁、channel、WaitGroup）
- **运行时比对**：发现无同步关系的冲突访问即报告 `WARNING: DATA RACE`，附两个调用栈
- 用法：`go run -race`、`go build -race`、`go test -race ./...`
- **注意**：只检测**实际执行到**的路径；生产有 5~10 倍开销，应在测试与 CI 中使用

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 并发任务执行（批量请求、并行计算） | goroutine、WaitGroup |
| 生产者消费者模型（日志处理、任务队列） | 有缓冲 channel、worker pool |
| 数据流管道（采集 → 清洗 → 聚合） | channel、fan-in/fan-out |
| 第三方 API 调用超时控制 | select、time.After、context.WithTimeout |
| 优雅停机（退出前排空在途任务） | context 取消、channel 关闭、WaitGroup |
| 共享计数器/指标统计保护 | Mutex、RWMutex |
| 并发爬虫（多源抓取汇总） | worker pool + fan-in |
| 多源设备数据并发采集 | 每设备 goroutine + channel + context |

**不适合**此阶段的事项：

- **分布式事务与分布式锁**：单机并发与跨节点一致性是两个层次，属 ph11 微服务与分布式范畴
- **微服务治理**（服务发现、集群级熔断限流）：ph11 覆盖，本阶段只做进程内并发
- **Kafka/Pulsar 等消息中间件深度**：属 ph19，channel 只是进程内通信
- **自研调度器/锁算法**：GMP 调度与 sync 原语已内置，不要重复造轮子

## 6. 代码示例

> 说明：示例均可直接运行（仅标准库，无第三方依赖），验证环境 Go 1.22.2（darwin/arm64）。每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，均为独立 Go module（各自子目录内自带 go.mod），运行命令见 examples/README.md；示例 5 必须用 `go run -race` 运行以演示数据竞争检测。

### 示例 1：goroutine + WaitGroup 并发求和

```go
package main
import (
    "fmt"
    "sync"
)
func sumChunk(nums []int, wg *sync.WaitGroup, result *int) {
    defer wg.Done()
    total := 0
    for _, n := range nums {
        total += n
    }
    *result = total
}
func main() {
    nums := make([]int, 1000000)
    for i := range nums {
        nums[i] = i + 1
    }
    const parts = 4
    chunkSize := len(nums) / parts
    results := make([]int, parts)
    var wg sync.WaitGroup
    for i := 0; i < parts; i++ {
        start := i * chunkSize
        end := start + chunkSize
        if i == parts-1 { end = len(nums) } // 最后一段收尾
        wg.Add(1)
        go sumChunk(nums[start:end], &wg, &results[i])
    }
    wg.Wait()
    total := 0
    for _, r := range results { total += r }
    fmt.Printf("1+2+...+1000000 = %d\n", total) // 500000500000
}
```

完整文件：`examples/ex01-waitgroup-sum/main.go`（`cd examples/ex01-waitgroup-sum && go run .`）

要点：每个 goroutine 写入 `results` 的**不同槽位**（`&results[i]`）——无锁也安全；并行度受 `parts` 控制，最后一段收尾避免整除截断。

### 示例 2：无缓冲 channel 的同步通信（worker 协作）

```go
package main
import (
    "fmt"
    "time"
)
func main() {
    done := make(chan string) // 无缓冲：完成信号必须被接收，发送才不阻塞
    go func() { // 数据采集 worker
        for i := 1; i <= 3; i++ {
            time.Sleep(50 * time.Millisecond)
            fmt.Printf("  采集第 %d 组数据\n", i)
        }
        done <- "采集完成" // 同步交接点：main 未接收前，这里一直阻塞
        fmt.Println("worker：信号已交接，继续清理")
    }()
    msg := <-done // 同步点：阻塞等待 worker 的信号
    fmt.Println("main 收到:", msg)
}
```

完整文件：`examples/ex02-unbuffered-channel/main.go`（`cd examples/ex02-unbuffered-channel && go run .`）

要点：无缓冲 channel 的收发是**配对交接**——发送方阻塞直到接收方就绪。"采集完成"一定出现在 main 的"收到"之前，这就是同步语义。

### 示例 3：select + time.After 超时控制

```go
package main
import (
    "fmt"
    "time"
)
func fakeFetch(name string, delay time.Duration, out chan<- string) {
    time.Sleep(delay)
    out <- name + " 的数据"
}
func main() {
    chA := make(chan string, 1) // 缓冲 1：无人接收时发送方也不永久阻塞
    chB := make(chan string, 1)
    go fakeFetch("数据源 A", 150*time.Millisecond, chA)
    go fakeFetch("数据源 B", 200*time.Millisecond, chB)
    select {
    case data := <-chA:
        fmt.Println("拿到:", data)
    case data := <-chB:
        fmt.Println("拿到:", data)
    case <-time.After(100 * time.Millisecond):
        fmt.Println("超时：100ms 内无数据，先做降级处理")
    }
    // 超时只是"放弃等待"——数据到达后仍可读取
    select {
    case data := <-chA:
        fmt.Println("稍后 A 返回:", data)
    case data := <-chB:
        fmt.Println("稍后 B 返回:", data)
    case <-time.After(500 * time.Millisecond):
        fmt.Println("两个数据源均未返回")
    }
}
```

完整文件：`examples/ex03-select-timeout/main.go`（`cd examples/ex03-select-timeout && go run .`）

要点：第一个 select 触发超时分支（两个数据源都慢于 100ms）；第二个 select 等到 A 在 150ms 返回——**time.After 只放弃本次等待，不杀死 goroutine**。真实项目更推荐 `context.WithTimeout` 主动取消。

### 示例 4：worker pool 任务队列（带 context 取消）

```go
package main
import (
    "context"
    "fmt"
    "sync"
    "time"
)
func worker(ctx context.Context, id int, jobs <-chan int, wg *sync.WaitGroup) {
    defer wg.Done()
    for {
        select {
        case <-ctx.Done(): // 取消信号优先退出
            fmt.Printf("worker %d 退出（原因: %v）\n", id, ctx.Err())
            return
        case j, ok := <-jobs:
            if !ok { fmt.Printf("worker %d 处理完所有任务，退出\n", id); return } // jobs 关闭且取空
            time.Sleep(20 * time.Millisecond) // 模拟任务耗时
            fmt.Printf("worker %d 完成任务 %d\n", id, j)
        }
    }
}
func main() {
    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel()
    const workers = 3
    jobs := make(chan int, 100)
    var wg sync.WaitGroup
    for i := 1; i <= workers; i++ {
        wg.Add(1)
        go worker(ctx, i, jobs, &wg)
    }
    go func() { // 任务派发（发送方）：ctx 取消时停止派发
        for j := 1; j <= 100; j++ {
            select {
            case jobs <- j:
            case <-ctx.Done():
                fmt.Println("ctx 已取消，停止派发任务")
                return
            }
        }
        close(jobs)
    }()
    wg.Wait() // 所有 worker 退出（正常耗尽或 ctx 取消）
    fmt.Println("worker pool 全部退出")
}
```

完整文件：`examples/ex04-worker-pool/main.go`（`cd examples/ex04-worker-pool && go run .`）

要点：worker 同时监听 `ctx.Done()` 与任务 channel——**取消与任务处理并存**，任一条件满足即退出，杜绝泄漏；派发方同样检查 ctx。运行可见：100ms 内只完成部分任务，随后 worker 以 `context deadline exceeded` 退出。

### 示例 5：Mutex 保护共享计数器 + race detector 演示

先看**无锁版本**（有数据竞争，别这样写）——`go run -race bad_counter.go` 必现 `WARNING: DATA RACE`：

```go
// bad_counter.go —— 数据竞争演示
package main
import (
    "fmt"
    "sync"
)
type BadCounter struct{ value int }
func (c *BadCounter) Inc() { c.value++ } // 多 goroutine 并发读写 → 数据竞争
func main() {
    var wg sync.WaitGroup
    c := &BadCounter{}
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for j := 0; j < 1000; j++ {
                c.Inc()
            }
        }()
    }
    wg.Wait()
    fmt.Println("无锁计数:", c.value, "（期望 100000，实际每次运行可能不同）")
}
```

**正确版本**用 Mutex 保护——`go run -race counter.go` 无警告、输出恒为 100000：

```go
// counter.go —— Mutex 保护共享计数器
package main
import (
    "fmt"
    "sync"
)
type Counter struct {
    mu    sync.Mutex
    value int
}
func (c *Counter) Inc() { c.mu.Lock(); defer c.mu.Unlock(); c.value++ }
func (c *Counter) Value() int { c.mu.Lock(); defer c.mu.Unlock(); return c.value }
func main() {
    var wg sync.WaitGroup
    c := &Counter{}
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for j := 0; j < 1000; j++ {
                c.Inc()
            }
        }()
    }
    wg.Wait()
    fmt.Println("加锁计数:", c.Value(), "（期望 100000）")
}
```

完整文件：`examples/ex05-race-counter/bad/main.go`（无锁版，`cd examples/ex05-race-counter && go run -race ./bad` 必现 DATA RACE）与 `examples/ex05-race-counter/good/main.go`（Mutex 版，`go run -race ./good` 无警告）

验证：`go run -race counter.go` 无 DATA RACE、输出恒为 100000；`go run -race bad_counter.go` 必现竞争报告——**race detector 是并发代码的必用验收工具**。

## 7. 总结

### 关键要点

1. **goroutine 不是无限便宜**：约 2KB 栈起步，需要生命周期管理——泄漏的 goroutine 及其引用对象永远无法回收
2. **channel 用于通信，mutex 用于保护共享状态**：传递数据用 channel，保护共享变量用互斥锁
3. **context 用于取消和超时传播**：ctx 作为第一个参数显式传递，`defer cancel()` 是铁律
4. **关闭 channel 应由发送方负责**：向已关闭 channel 发送、重复关闭都会 panic；接收方用 `v, ok := <-ch` 或 range 消费
5. **无缓冲 channel 是同步点**：收发配对交接，构成 happens-before 屏障——"通过通信共享内存"的底层保障
6. **select 是 channel 的多路复用器**：就绪 case 随机选择，`time.After` 实现超时，`default` 实现非阻塞
7. **WaitGroup 等待完成、Mutex 保护临界区**：Add 在 Wait 前、锁用 defer 成对释放——顺序错了就是死锁或竞争
8. **worker pool + fan-in/fan-out 是组合范式**：固定 worker 控制并发度，close 广播结束，汇聚用 WaitGroup 收口
9. **race detector 是必用工具**：`go test -race ./...` 应进 CI——但它只检测实际执行到的路径
10. **main 返回程序即退出**：主 goroutine 必须等待/协调所有后台 goroutine

### 跨语言对比：并发模型

| 维度 | Go（CSP） | Java（线程） | Python（asyncio） | Rust（async） | C（pthread） |
|------|-----------|--------------|-------------------|---------------|--------------|
| 并发原语 | goroutine | Thread | coroutine/task | task/future | pthread_t |
| 调度方式 | M:N 运行时调度（GMP） | 1:1 OS 线程 | 单线程事件循环 | M:N 运行时（tokio） | 1:1 OS 线程 |
| 通信方式 | channel（CSP） | 共享内存 + 锁 | await 调用 + queue | async/await + channel | 共享内存 + 锁/条件变量 |
| 并发规模 | 百万级 | 千级（线程昂贵） | 十万级协程 | 百万级 | 百~千级 |
| 数据竞争防护 | race detector（运行时检测） | 无（靠 JMM 自觉） | 单线程天然无竞争 | 编译器强制（Send/Sync） | 无（全靠自觉） |
| 取消机制 | context 传播 | interrupt/标志位 | task.cancel() | CancellationToken | pthread_cancel |

### 阶段验收清单

- [ ] 能写出**无 goroutine 泄漏**的并发代码：每个 goroutine 都有明确退出路径（channel 关闭 / context 取消 / WaitGroup 等待）
- [ ] 能使用 **context 控制生命周期**：取消与超时正确传播，worker 检查 `ctx.Done()` 优雅退出
- [ ] 能用 **race detector 检查并发代码**：`go run -race` / `go test -race ./...` 发现并修复数据竞争
- [ ] 能区分 **channel 与 mutex** 的适用场景，正确执行关闭规则（发送方负责关闭）
- [ ] 能实现 **worker pool 与 fan-in/fan-out**，用 select 完成超时控制

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：worker pool、并发爬虫、任务超时控制、数据采集并发处理共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**并发日志处理器**（多源日志并发写入、按级别过滤/聚合、超时刷新与优雅关闭——channel 队列 + worker pool + context）。建议完成练习后再动手。

- [ ] 完成 exercises 全部练习并对照参考实现复盘
- [ ] 独立完成 project（通过 README 验收标准）

### 下一阶段

[标准库阶段](../ph07-stdlib/07-stdlib.md) —— os/path/filepath、encoding/json、net/http、testing 深入等。
