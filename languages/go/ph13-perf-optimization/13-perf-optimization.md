# Go 性能优化阶段

> 面向"让 Go 程序从'能跑'变成'快且稳'"——本阶段把 ph12 部署上线后的服务升级为**可度量、可定位、可优化**的产物：用 benchmark 量化（ns/op / B/op / allocs/op 三列）、用 pprof / trace 定位（CPU、内存、goroutine、mutex、block 五个视角）、用逃逸分析理解内存去向、用 sync.Pool 与减少锁竞争/分配落地优化——最终能交付一份「先 profile 再优化、用数据验证效果」的性能调优报告。

## 1. 概述

Go 性能优化阶段的目标是（引用 Roadmap）：**能分析和优化 Go 程序性能**。ph08 测试阶段已经把 benchmark 三列指标（ns/op、B/op、allocs/op）当作"快不快、分配多不多"的初判，本阶段把它升级为完整闭环——**测量（benchmark）→ 定位（pprof/trace）→ 优化（逃逸分析、sync.Pool、减少锁竞争与分配）→ 验证（再跑 benchmark 对比前后）**。ph12 部署上线的服务在本阶段获得"调优"能力：/metrics 里的延迟直方图只能告诉你"慢"，本阶段回答"慢在哪一行、为什么慢、怎么改、改完快了多少"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 量化 | benchmark 三列指标（ns/op / B/op / allocs/op）、-benchmem、-benchtime、RunParallel 并发基准、防编译器优化（sink 落地） |
| 定位 | pprof 五类 profile（CPU / heap / goroutine / mutex / block）+ `go tool pprof -top` + execution trace（runtime/trace） |
| 内存 | 逃逸分析（`-gcflags='-m'`）、GC 基础（触发条件、分配压力）、减少不必要分配（预分配、strings.Builder、strconv 免装箱） |
| 并发 | goroutine 泄漏检测与修复、锁竞争（全局锁/分片锁/atomic）、mutex/block profile 定位等待点 |

本阶段的核心信念来自四条必会概念：**先 profile，再优化**——不测量就动手是猜测，profile 告诉你热点在哪一行，优化才有据；**分配次数会影响 GC 压力**——每次堆分配都是 GC 要扫描的对象，allocs/op 是比 B/op 更敏感的信号；**goroutine 泄漏也是性能问题**——泄漏的 goroutine 连同其栈常驻内存，堆积到一定量就是 OOM；**sync.Pool 只适合可复用临时对象**——它复用的是"用完可弃"的对象，不是缓存长期数据的容器，而且不是无条件更快（本阶段实测其边界，见 3.5）。

这个阶段只涉及"测量 → 定位 → 减少分配/竞争 → 验证"的性能方法论闭环，**不涉及 Go runtime 底层实现机制（GMP 调度器、GC 算法细节、channel/map/slice/interface 底层布局、reflect/unsafe/cgo——那些是 ph14 高级 Go 阶段的内容，roadmap 第 14 节，目录待建）、PGO 与生产流量指导优化（profile-guided optimization 属 ph16 PGO 与高级性能优化阶段，roadmap 第 16 节，目录待建）和语言级并发模型本身（goroutine/channel/context 的用法属 ph06 并发编程阶段）** — 本阶段用标准库工具就能完成全部量化与定位，GC/调度"为什么长这样"留给 ph14，PGO"用生产 profile 指导编译"留给 ph16。

## 2. 来源与演变

**Go 性能工具链的源头是 Google 内部的大型分布式系统运维经验**：2007 年 Go 项目启动时，Google 的 C++ 服务已经吃透了"先测量再优化"的教训——于是 benchmark 直接进标准库 testing 包、pprof（Google 的 profile 查看器）与 Go 深度绑定、execution trace 从调度器设计的第一天就规划进去。**设计哲学：性能是工程问题不是玄学——测量工具与运行时同源，profile 数据与调度器/GC 直接打通**。这解释了为什么 Go 的性能工具全部零第三方依赖：它们是语言的一部分，不是事后挂上的插件。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Go 1.0 发布 | 2012 | testing 包自带 Benchmark 支持，性能测量进标准库（-benchmem 后补） |
| sync.Pool 引入 | 2014 (Go 1.3) | 临时对象复用，缓解 GC 压力（早期实现有锁，竞争开销大） |
| runtime/trace 引入 | 2015 (Go 1.5) | 执行轨迹：调度、GC、阻塞事件的可视化；GC 并发化大幅改进 |
| 逃逸分析大幅改进 | 2016 (Go 1.7) | 编译器换 SSA 后端，大量变量从堆搬回栈，零分配函数变多 |
| pprof 交互式 UI 普及 | 2017-2018 | google/pprof 并入 go tool pprof，浏览器交互（-http）与火焰图成为标配 |
| sync.Pool 重写 | 2019 (Go 1.13) | 引入 victim cache（对象跨 GC 保留一代）+ 无锁私有槽，竞争开销大降——[设计解读](https://my.oschina.net/u/4628563/blog/4723989) |
| 内存分配器换代 | 2025 (Go 1.24) | allocation header 方案，小对象分配开销进一步下降 |

本文示例以 **go1.25.6** 为基线（本环境实际跑通——本阶段全部示例、练习、项目与实测数字均为 go1.25.6 / darwin / arm64 / Apple M4 Pro 上零第三方依赖的实测结果，可离线复现），验证工具链 go1.25.6（`go build -gcflags='-m'`、`go test -bench`、`go tool pprof`、`go tool trace` 全部随发行版自带）。benchmark/pprof/逃逸分析的语法是本阶段最稳定的部分：`go test -bench=. -benchmem` 与 `go tool pprof -top` 的用法自 Go 1.x 中期至今基本未变，工具链升级只会让数字更好看、不会让命令失效——这也是本阶段练习可以放心标注「已验证」的原因。

## 3. 语法与参数

### 3.1 benchmark：三列指标与"防优化"纪律

**benchmark 是性能优化的尺子**——一切优化效果都要用它量化。三列指标各有含义：**ns/op**（每次操作耗时）、**B/op**（每次操作分配字节数）、**allocs/op**（每次操作分配次数）。其中 **allocs/op 是 GC 压力的直接源头**（roadmap 必会概念），同样 1 KB 的分配，1 次还是 100 次，对 GC 的影响完全不同：

```go
// 完整可运行版见 examples/ex01-benchmark/main_test.go（节选）
// 基准结果必须"落地"到包级变量：防止编译器把整个计算优化掉
var sinkStr string

func BenchmarkConcatPlus(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = ConcatPlus(1000) // sink 落地：结果必须真被使用
	}
}
```

要点：**`b.N` 由框架自动调节**（让每次基准跑约 1 秒），不要手写固定次数；**`-benchtime=2000x`** 可固定迭代次数（便于复现、对比）；**`-benchmem`** 打开 B/op 与 allocs/op 两列；**`b.RunParallel`** 模拟并发（多 P 同时执行，最能体现锁竞争与 per-P 缓存差异）；**`b.ResetTimer()`** 把准备工作（如生成输入数据）排除在计时外。**坑：计算结果不用会被编译器整个删掉**——必须赋给包级变量（sink）或 `runtime.KeepAlive`。

**实测（ex01，1000 次迭代/op）**——字符串拼接三写法与 slice 预分配：

| 基准 | ns/op | B/op | allocs/op |
|------|-------|------|-----------|
| `ConcatPlus`（`+=` 拼接） | 74947 | 530281 | 999 |
| `ConcatBuilder`（strings.Builder + Grow） | 1975 | 1024 | 1 |
| `ConcatJoin`（strings.Join） | 6701 | 1024 | 1 |
| `AppendNoPrealloc`（append 自然扩容） | 2479 | 25208 | 12 |
| `AppendPrealloc`（make 预分配容量） | 781.9 | 8192 | 1 |

**结论**：`+=` 是 O(n²)（每轮整体拷贝新串）且 999 次分配——Builder 快 38 倍、Join 快 11 倍且都只要 1 次分配；slice 预分配省 11 次分配、快 3.2 倍。**"快不快"看 ns/op，"分配压力"看 allocs/op——本阶段全部优化以这两列收尾验证**。

### 3.2 pprof：五个 profile 视角

**pprof 回答"时间花在哪、内存分配在哪、谁在等"**。五种 profile 各有用途：

| profile | 采集方式 | 回答什么问题 |
|---------|---------|-------------|
| CPU | `pprof.StartCPUProfile` / `net/http/pprof` 的 `/debug/pprof/profile` | 时间花在哪个函数（100Hz 采样） |
| heap | `pprof.WriteHeapProfile` / `/debug/pprof/heap` | 内存分配来自哪个函数（inuse/alloc 两种视角） |
| goroutine | `pprof.Lookup("goroutine")` / `/debug/pprof/goroutine` | 有多少 goroutine、卡在哪个函数（泄漏排查） |
| mutex | `SetMutexProfileFraction` + `Lookup("mutex")` | 锁竞争：等待发生在哪一行 |
| block | `SetBlockProfileRate` + `Lookup("block")` | 阻塞：channel/锁/IO 等待在哪一行 |

```go
// 完整可运行版见 examples/ex03-pprof-cpu-mem/main.go（节选）
// fib 是故意的 CPU 热点：指数递归，CPU profile 里应占据绝对主导
//
//go:noinline
func fib(n int) int {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}
```

采集后统一用 `go tool pprof -top -nodecount=3 <程序> <profile>` 看前三名（本环境实测，见 6 章示例 3）：CPU profile 里 `main.fib` 占 93.64% flat（热点函数一目了然）；heap profile 里 `main.makeGarbage` 占 59.99% inuse（分配来源一目了然）。**要点**：CPU profile 是 100Hz 采样，程序跑太短会采不到样本（Total samples = 0）；heap profile 建议在不开 CPU profile 的单独一次运行里采集，否则 pprof 自身的分配会混进结果。生产服务用 `net/http/pprof` 挂 `/debug/pprof/` 端点，压测时采集（ph12 的压测入口正是 /metrics 之外的这条线）。

### 3.3 execution trace：调度与阻塞的时间线

**execution trace 记录"goroutine 何时被调度、何时阻塞、GC 何时跑"的完整时间线**（区别于 pprof 的"快照统计"，trace 是"过程录像"）：

```go
// 完整可运行版见 examples/ex06-goroutine-leak-trace/main.go（captureTrace 函数，节选）
if err := trace.Start(f); err != nil {
	return err
}
work()        // 要观察的工作
trace.Stop()  // 停止采集，文件交给 go tool trace 查看
```

`go tool trace <文件>` 打开浏览器 UI（goroutine 时间线、GC 事件、网络阻塞）。**它和 pprof 的分工**：pprof 告诉你"哪里占时间"（统计），trace 告诉你"为什么这段时间在等"（事件序列）——比如一个 CPU profile 看不出来的"goroutine 大部分时间在休眠"现象，trace 一眼就能看到阻塞区间。trace 的浏览器 UI 属交互式查看器，本环境只验证了文件生成（magic header `go 1.25 trace`），UI 标注「未在本环境验证」。

### 3.4 逃逸分析：变量住栈还是住堆

**逃逸分析（escape analysis）是编译器在编译期裁决"每个变量住栈还是住堆"**——住栈：函数返回即回收，零成本；住堆：由 GC 管理，每次分配都有成本。裁决规则：**地址逃出函数作用域（返回/存入全局/传给可能长期持有的位置）→ 住堆；对象太大栈放不下 → 住堆；装箱进 interface{} 传给不内联的函数 → 住堆**。

```go
// 完整可运行版见 examples/ex02-escape-analysis/main.go（节选）
// makePoint 逃逸：返回局部变量地址，p 必须活到调用者手里 → moved to heap（1 次分配）
//
//go:noinline
func makePoint() *Point {
	p := Point{X: 1, Y: 2}
	return &p
}
```

用 `go build -gcflags='-m' .` 打印裁决（本环境实测输出，行号与本文件一致）：

```text
./main.go:36:2: moved to heap: p          ← makePoint：返回局部变量地址 → 堆
./main.go:52:6: moved to heap: b          ← bigBuf：1 MiB 对象太大，栈放不下
./main.go:59:17: len(s) escapes to heap   ← printLen：len(s) 装箱进 interface{} 参数
```

**实测对照**（同数据、不同返回方式，-benchtime=1000000x）：

| 基准 | ns/op | B/op | allocs/op |
|------|-------|------|-----------|
| `BenchmarkEscaped`（makePoint 返回指针） | 9.13 | 16 | 1 |
| `BenchmarkStack`（makePointVal 按值返回） | 0.80 | 0 | 0 |

按值返回留栈，**快约 11 倍、0 分配**。**坑：逃逸裁决是"调用上下文相关"的**——`makePointVal()` 单独看不逃逸，但传给 `fmt.Println` 时（装箱 interface{}）照样 `moved to heap`（`-m` 输出可见）。所以"这个函数分配不分配"不能只看函数体，要看调用链。`//go:noinline` 在本示例里用来**固定裁决**（防止内联掩盖逃逸行为），生产代码不要乱加。

> 逃逸分析只是本阶段"理解分配从哪来"的视角；**编译器的完整优化管线（SSA、内联、devirtualization 等）属于 ph14 高级 Go 阶段**，这里只需会读 `-m` 输出、能判断"怎么改让它不逃逸"。

### 3.5 sync.Pool：复用临时对象

**sync.Pool 缓存"用完可弃"的临时对象**，让高频短生命周期的对象免于反复分配——三个要素：**Get（借）→ Reset（用前清空，池里对象是脏的）→ Put（还）**：

```go
// 完整可运行版见 examples/ex04-sync-pool/main.go（节选）
// ProcessPool 从池里借缓冲：热路径零分配（池命中时 New 不执行）
func ProcessPool(data []byte) int {
	buf := bufPool.Get().(*bytes.Buffer)
	buf.Reset() // 关键：池中的对象带着上一次使用的内容，不复位就会串数据
	defer bufPool.Put(buf)
	buf.Write(data)
	return checksum(buf)
}
```

**实测（ex04，并发 RunParallel）**：

| 场景 | 朴素版（每次新建 Buffer） | Pool 版 | 差异 |
|------|--------------------------|---------|------|
| 大负载（4090 B） | 821.0 ns/op，4096 B，1 allocs | 16.32 ns/op，0 B，0 allocs | Pool 快约 50 倍 |
| 小负载（约 50 B） | 32.67 ns/op，64 B，1 allocs | 5.09 ns/op，0 B，0 allocs | Pool 快约 6.4 倍 |

**sync.Pool 什么时候值得用（边界实测）**：上表朴素版每次逃逸分配（64 B 或 4096 B），Pool 稳赢。但**对象能完全留在栈上时（如固定小数组，零分配），朴素版反而更快**——本环境附加实验（单线程）：栈数组版 2.37 ns/op、Pool 版 8.28 ns/op，**朴素快约 3.5 倍**（Pool 的 Get/Put 簿记是纯开销）。正确判断顺序：① 逃逸分析说"能留栈"→ 别用 Pool，直接用栈变量；② 必须堆分配且创建频繁、分配大 → Pool 摊销分配成本；③ 小对象且低频 → 不值得。**另外三条纪律**：Pool 会被 GC 清空（只存临时对象，不能当长期缓存）；Get 后必须 Reset；对象生命周期必须"用完可弃"（不能持有长期引用）。

### 3.6 减少锁竞争与不必要分配

**锁竞争是并发性能的三大支柱之一（roadmap 必会概念）**——同一把锁被多个 goroutine 抢时，等待者要么自旋要么挂起，吞吐随竞争上升而崩。三种策略（完整代码见 examples/ex05-lock-contention）：

| 策略 | 手段 | 代价 |
|------|------|------|
| 全局互斥锁 | 一把 `sync.Mutex` 保护所有状态 | 竞争最重，8 goroutine 全排队 |
| 分片锁 | 按 key 散列到 N 片，每片一把锁 | 竞争摊薄为 1/N；多 N 把锁 + 散列开销 |
| atomic | `atomic.AddInt64` 一条 CPU 指令 | 只能做单字段复合状态；高竞争下缓存行乒乓 |

```go
// 完整可运行版见 examples/ex05-lock-contention/main.go（节选）
// AtomicCounter 无锁：atomic.AddInt64 一条 CPU 指令，无 goroutine 挂起
type AtomicCounter struct {
	n atomic.Int64
}

func (c *AtomicCounter) Inc()        { c.n.Add(1) }
func (c *AtomicCounter) Load() int64 { return c.n.Load() }
```

**实测（-benchtime=1s 时长基准，-cpu=8，三次均值）**：全局锁 ~95.2 ns/op → 分片锁 ~61.4 ns/op（快 1.5 倍）→ atomic ~34.9 ns/op（快 2.7 倍）。**注意**：① 分片收益取决于"锁在单次操作里的成本占比"——若操作本身重（如 map 写），分片收益会被淹没（练习 sol-04 实测：洗牌 key 下缓存分片快 1.7 倍，而同步轮询同一 key 时反而更慢）；② 分片必须做**缓存行隔离**（padding），否则 false sharing 让核间缓存同步抵消分片收益；③ atomic 无锁无挂起通常最快，但只能原子地操作单个字段。**动手前先用 mutex/block profile 确认"锁是不是瓶颈"**——本环境实测 mutex profile 能精确聚出 `main.go:99`（`mu.Lock()`）这一行。

**减少不必要分配**（不涉及并发，但同属"分配压力"主题）：slice 预分配（3.1 实测 12→1 allocs）、字符串拼接用 Builder/Join（3.1）、数字转字符串用 `strconv.AppendInt` 免装箱（练习 sol-02 的 FastHandler）、JSON 用具名 struct 而非 map（练习 sol-01 实测 allocs 20910→8009）。

## 4. 底层原理

### 4.1 GC 触发与"分配压力"从何而来

```text
程序分配堆对象（逃逸分析的"住堆"）→ 堆大小增长
→ 达到触发阈值（默认 GOGC=100：堆翻倍即触发）→ 触发一次 GC
→ GC 标记（并发）→ 清扫（并发）→ 堆回落，等待下次增长
分配次数越多 → 触发越频繁 → GC 占用的 CPU 时间越多 → 程序越慢
```

要点：**GC 不是"定时器"，是"堆增长到阈值就触发"**——所以优化分配（allocs/op 下降、B/op 下降）的直接收益是 GC 触发频率下降；benchmark 里 `B/op` 与 `allocs/op` 两列正是"这台程序会给 GC 多大压力"的预测量。GC 的实现机制（三色标记、混合写屏障、并发清扫的细节）属 ph14，本阶段只需这个"分配→触发→占用 CPU"的因果链——它解释了为什么"减少不必要分配"是性能优化的第一优先项。

### 4.2 逃逸分析：编译器视角的"住哪里"裁决

```text
源代码 ──▶ 逃逸分析（编译期静态分析）──▶ 住栈：函数帧回收即释放，零成本
                                       └──▶ 住堆：GC 管理，每次分配有成本
裁决依据（任一命中即住堆）：
  · 地址逃出函数作用域（返回、存入全局/堆对象）
  · 对象大小超过栈帧容量上限（本机 1 MiB 量级）
  · 装箱进 interface{} 且传给无法内联的函数
  · 泄漏进全局变量或长期持有的容器
```

要点：**逃逸是"证据链"不是"规则表"**——编译器沿着调用链看地址是否可能逃逸；`-gcflags='-m'` 打印的就是这条证据链的结论。这也是为什么 `makePointVal()` 在基准里 0 分配、在 `fmt.Println(makePointVal())` 里逃逸——调用上下文变了，证据链变了。**给优化的启示**：热点函数尽量按值传递小对象、避免 `&` 逃逸、避免为拼接临时装箱——但先用 `-m` 确认，别凭感觉改。

### 4.3 锁竞争、分片与缓存行（false sharing）

```text
全局锁：8 个 goroutine 抢 1 把锁 → 等待队列 + 自旋/挂起，吞吐崩
分片锁：key % 16 → 竞争摊薄为 16 片，多数获取无竞争直接进入
缓存行（false sharing）：不同分片的计数若落在同一缓存行（64 B），
  一个分片写 → 整行失效 → 其他核同步 → 分片形同虚设
  解法：每分片补齐 64 B 对齐（padding），让不同分片住不同缓存行
```

要点：**分片锁的本质是"把锁的粒度变小"**——竞争概率从 1（所有人抢一把）降到 1/N，锁等待时间随竞争概率下降；但分片引入了散列开销与 false sharing 风险，所以分片收益不是白给的（实测见 3.6：计数器 1.5 倍、缓存 1.7 倍、设计不当反而不如全局锁）。**atomic 无锁的本质是"把锁换成 CPU 指令"**——`AddInt64` 是单指令原子操作，无等待队列；但高竞争下多个核反复写同一地址，缓存行在核间乒乓，可能比分片锁更慢（本机 8 P 下 atomic 仍最快，14 P 高竞争未必，以本机 profile 为准）。

## 5. 使用场景

| 场景 | 用什么 | 对应知识点 |
|------|--------|-----------|
| 上线前压测、上线后优化 | benchmark（快不快）+ pprof（慢在哪） | 3.1 / 3.2 |
| 服务内存涨不停 / OOM 前兆 | heap profile（inuse 视角）+ goroutine profile | 3.2 / 3.3 |
| 并发服务吞吐上不去 | CPU profile → 锁竞争？→ mutex/block profile | 3.2 / 3.6 |
| 请求延迟高但 CPU 不高 | execution trace（看阻塞区间） | 3.3 |
| 高频创建大临时对象（JSON 序列化缓冲等） | sync.Pool（先确认对象必须堆分配） | 3.5 |
| 热点函数反复分配 | 逃逸分析 → 按值/预分配/免装箱改造 | 3.1 / 3.4 |

**不适合**此阶段的事项：

- **Go runtime 底层机制**（GMP、GC 算法、slice/map 内部布局）：属 ph14——本阶段只"用工具看现象"，不拆实现
- **PGO（profile-guided optimization）**：属 ph16——本阶段的 profile 数据是它的输入，但"用 profile 指导编译器"是另一套流程
- **并发模型的用法本身**（goroutine/channel/context 设计）：属 ph06——本阶段默认读者会写并发，只优化它的性能

**选型参考：性能工具链**

| 维度 | benchmark | pprof | trace | sync.Pool |
|------|-----------|-------|-------|-----------|
| 回答 | 快不快、分配多不多 | 时间/内存/等待在哪 | 阻塞的时间线 | 分配能不能省 |
| 时机 | 优化前后必跑 | 优化中定位用 | 性能反常时用 | 确认分配是瓶颈后用 |
| 成本 | 低（写基准） | 低（采样） | 中（文件大、UI 分析） | 低（代码量小） |
| 误用风险 | 优化掉计算结果 | 采样太短没数据 | 不常用生疏 | 该留栈的上了 Pool（3.5 边界） |

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：Go 的 pprof/trace 与运行时同源、零依赖、开箱即用；Java 对应 JFR（JDK Flight Recorder）+ JMC 分析器（采集与查看分离、事件驱动）；Rust 生态靠 criterion（基准）+ perf/flamegraph（剖析，非语言内置）；Python 靠 cProfile（纯 Python 采样）与 py-spy（生产进程注入）。**Go 的差异化优势是"工具链与运行时同源"**——profile 数据能直接映射到调度器/GC 内部事件（trace 里能看到 goroutine 调度细节），这是解释型语言和 JVM 生态都做不到的深度；代价是工具只理解 Go，不能像 perf 那样剖析内核态。

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），全部零第三方依赖。六个示例均通过 `go vet ./...`、`go test ./...`、`go test -race ./...`；实测数字见 examples/README.md（下表"实测"列为本环境输出节选）。

| 示例 | 一句话说明 | 实测（节选） |
|------|-----------|-------------|
| ex01-benchmark | 字符串拼接三写法与 slice 预分配的 benchmark 量化 | `+=` 999 allocs vs Builder 1 alloc，快 38 倍 |
| ex02-escape-analysis | 逃逸分析：`-m` 打印裁决，堆 vs 栈基准对照 | 返回指针 1 alloc / 9.13 ns vs 按值 0 alloc / 0.80 ns |
| ex03-pprof-cpu-mem | runtime/pprof 采集 CPU 与 heap profile | CPU：fib 占 93.64%；heap：makeGarbage 占 59.99% |
| ex04-sync-pool | sync.Pool 复用临时缓冲 + 适用边界 | 4 KiB 负载快 50 倍；栈对象场景朴素更快（3.5 倍） |
| ex05-lock-contention | 三种同步策略 + mutex/block profile | 全局 95.2 → 分片 61.4 → atomic 34.9 ns/op |
| ex06-goroutine-leak-trace | goroutine 泄漏检测与修复 + execution trace | 20 次超时调用泄漏 20 个 goroutine，profile 聚出泄漏行 |

### 示例 1：benchmark 三列指标（ex01-benchmark）

```go
// examples/ex01-benchmark/main.go —— 三种字符串拼接写法（节选）
// ConcatPlus 用 += 拼接：每轮产生一个新字符串（旧串整体拷贝），O(n²) 且每轮分配
func ConcatPlus(n int) string {
	var s string
	for i := 0; i < n; i++ {
		s += "x"
	}
	return s
}
```

运行：`cd examples/ex01-benchmark && go test -run='^$' -bench=. -benchmem -benchtime=2000x`（实测见 3.1 表）。**教学点**：同一结果三种写法，allocs/op 从 999 降到 1——优化先找"哪里在分配"，再决定用什么写法。

### 示例 2：逃逸分析（ex02-escape-analysis）

```go
// examples/ex02-escape-analysis/main.go —— 返回指针 vs 按值返回（节选）
// makePointVal 不逃逸：按值返回，p 留在栈上，零分配（与 makePoint 逐行对照）
//
//go:noinline
func makePointVal() Point {
	p := Point{X: 1, Y: 2}
	return p
}
```

运行：`go build -gcflags='-m' .` 打印裁决（实测输出见 3.4）；`go test -run='^$' -bench=. -benchmem -benchtime=1000000x` 看堆/栈的 allocs 差异。**教学点**：`-m` 是裁决证明，benchmark 是代价证明——两者配套用。

### 示例 3：pprof 定位热点（ex03-pprof-cpu-mem）

```go
// examples/ex03-pprof-cpu-mem/main.go —— 采集 CPU profile 的入口（节选）
if err := pprof.StartCPUProfile(f); err != nil {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
fmt.Println("cpuWork:", cpuWork()) // 被剖析的工作
pprof.StopCPUProfile()
```

运行（多步，本环境实测）：

```text
# 1. 构建并采集 CPU profile
go build -o /tmp/ex03 .
/tmp/ex03 -cpuprofile=/tmp/ex03-cpu.pprof
# 2. 查看热点（实测：main.fib 93.64%）
go tool pprof -top -nodecount=3 /tmp/ex03 /tmp/ex03-cpu.pprof
# 3. heap profile 同理（单独一次运行采集）
/tmp/ex03 -memprofile=/tmp/ex03-heap.pprof
go tool pprof -top -nodecount=3 /tmp/ex03 /tmp/ex03-heap.pprof
```

**教学点**：CPU profile 看"时间在哪"，heap profile 看"内存来自哪"——本示例故意构造两个热点（递归 fib、反复造 string），练习"读 -top 输出定位热点函数"。

### 示例 4：sync.Pool（ex04-sync-pool）

```go
// examples/ex04-sync-pool/main.go —— Get/Reset/Put 三要素（节选）
// bufPool 复用 *bytes.Buffer：New 只在池空时调用；对象在 GC 后可能被清空，随时能新建
var bufPool = sync.Pool{
	New: func() any { return new(bytes.Buffer) },
}
```

运行：`go test -v ./...`（含"不复位会串数据"与并发正确性测试）；`go test -run='^$' -bench=. -benchmem -benchtime=100000x`。**教学点**：实测的 50 倍差距 + 边界实验（栈对象场景朴素更快）——Pool 的价值与边界各占一半，详见 3.5 的判断顺序。

### 示例 5：锁竞争与 profile（ex05-lock-contention）

```go
// examples/ex05-lock-contention/main.go —— 分片锁（节选）
// ShardedCounter 分片锁：按 key 散列到 16 个分片，竞争概率降为 1/16
type ShardedCounter struct {
	s [shards]struct {
		mu sync.Mutex
		n  int64
		_  [40]byte // 缓存行 padding：避免 false sharing
	}
}
```

运行：`go test -run='^$' -bench=. -benchtime=1s -cpu=8`（固定 8 P 放大竞争）；`go run .` 打印 mutex/block profile 文本。**教学点**：三种策略的实测排序 + profile 精确到行——"优化锁"前先确认锁是瓶颈。

### 示例 6：goroutine 泄漏与 trace（ex06-goroutine-leak-trace）

```go
// examples/ex06-goroutine-leak-trace/main.go —— 泄漏版发送方（节选）
// leakySend 泄漏版：结果 channel 无缓冲，调用方超时返回后，这里的发送永远阻塞
func leakySend(work func() int, timeout time.Duration) (int, bool) {
	ch := make(chan int) // 无缓冲：发送方必须有接收方配对
	go func() {
		ch <- work() // 调用方放弃后，这行永远阻塞
	}()
	select {
	case v := <-ch:
		return v, true
	case <-time.After(timeout):
		return 0, false // 超时返回——goroutine 被抛弃，泄漏发生
	}
}
```

运行：`go run .`（实测：goroutine 数 1 → 21，泄漏栈聚在 `main.go:31`）；`go test -v ./...` 验证"泄漏版增长、修复版不增长"。**教学点**：检测三步（NumGoroutine 计数 → profile 看栈 → 修复后重测）+ 修复手段（缓冲 channel；更完整的 context 取消属 ph06）。

## 7. 总结

### 关键要点

1. **先 profile，再优化**（必会概念）：不测量就动手是猜测——benchmark 量化"快不快"，pprof/trace 定位"慢在哪一行"，优化后必须重跑 benchmark 验证
2. **分配次数影响 GC 压力**（必会概念）：allocs/op 是比 B/op 更敏感的信号；减少分配的三大抓手——预分配（make cap）、免装箱（strconv.AppendInt）、具名 struct 替代 map
3. **goroutine 泄漏也是性能问题**（必会概念）：无缓冲 channel + 调用方提前放弃 = 发送方永久阻塞；NumGoroutine 计数 + goroutine profile 定位 + 缓冲/context 修复
4. **sync.Pool 只适合可复用临时对象**（必会概念）：Get → Reset → Put 三要素；GC 会清池、对象用完可弃；能留栈的对象不该上 Pool（实测边界：栈版 2.37 ns vs Pool 8.28 ns）
5. **pprof 五视角各管一段**：CPU（时间）、heap（内存）、goroutine（泄漏）、mutex（锁竞争）、block（阻塞）；profile 是"快照统计"，trace 是"过程录像"
6. **减少锁竞争的收益取决于锁的成本占比**：计数器分片快 1.5 倍、atomic 快 2.7 倍；带散列+map 写的缓存分片收益被操作成本稀释（sol-04 实测 1.7 倍）；动手前先看 mutex profile
7. **逃逸裁决是调用上下文相关的**：`-gcflags='-m'` 打印证据链结论；按值返回留栈（快 11 倍、0 alloc），装箱/大对象/地址外传必逃逸
8. **基准必须防优化**：结果落地到包级变量（sink），否则编译器把整个计算删掉，测出假数字

### 阶段验收清单

- [ ] 能写 benchmark 并读三列指标：`go test -bench=. -benchmem`，能解释 ns/op、B/op、allocs/op 各自的含义与"哪个是 GC 压力源"
- [ ] 能生成并阅读 pprof：CPU/heap profile 用 `go tool pprof -top` 定位热点函数（示例 3 实测流程复现）
- [ ] 能解释逃逸分析输出：`go build -gcflags='-m'` 的 `moved to heap` / `escapes to heap` 对应哪种代码模式（示例 2）
- [ ] 能用 benchmark 验证优化效果：同一函数的朴素版与优化版对比，能说出优化改了什么、省了什么（练习 1/2）
- [ ] 能排查 goroutine 泄漏：NumGoroutine 计数 + goroutine profile 定位泄漏点 + 修复后验证数量回落（练习 3）
- [ ] 能优化锁竞争：说清全局锁/分片/atomic 的取舍与实测代价；用 mutex/block profile 确认锁是瓶颈（练习 4 / 示例 5）
- [ ] 能判断 sync.Pool 该不该用：按 3.5 的判断顺序（能留栈？高频？大对象？）给出结论，不盲目上 Pool
- [ ] 能完成 10 万行日志解析优化并量化：项目验收标准（见下）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap「练习」小节一一对应：

1. **优化 JSON 解析**（★★）：map 版 vs 具名 struct 版，benchmark 量化（参考实现实测：快约 1.6 倍、allocs 20910→8009）
2. **分析高并发接口**（★★★）：先 pprof 定位再优化 handler 响应体拼装（参考实现实测：热点函数快约 2~3 倍）
3. **查 goroutine 泄漏**（★★）：构造泄漏、profile 定位、缓冲 channel 修复（参考实现实测：40 发 20 泄漏）
4. **优化锁竞争**（★★★）：全局锁 vs 分片锁缓存，含基准设计的坑（key 洗牌 + 每 worker 错位；参考实现实测：快约 1.7 倍）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**日志解析性能优化**（roadmap 推荐项目）——生成 10 万行合成日志，用三种解析实现（map / struct / 手写扫描）解析同一批数据，量化耗时与分配差异并校验结果一致。**实测**：manual 版比 naive 版快约 5.8 倍（1075 → 185 ns/行）、allocs 28984 → 1、分配 -96%；roadmap 另一个推荐项目「高并发接口压测与优化」的完整方法论（profile → 优化 → 复测）已由练习 2 覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（10 万行 < 1s、三版结果一致、`go test -race ./...` 通过）

### 下一阶段

**ph14+（高级 Go 阶段，roadmap 第 14 节，目录待建）——本阶段是当前已建目录（ph01~ph13）的最后一个阶段**，ph14~ph21 的阶段目录尚未建立（roadmap 见 [`languages/go/go.md`](../go.md)）。后续可深入 **Go 底层机制**方向：GMP 调度器与 GC 算法实现、channel/map/slice/interface 的底层布局、defer/panic/recover 原理、reflection/unsafe/cgo——本阶段攒下的 profile 数据与「分配/竞争」的实证观察，正是 ph14 理解"调度器为什么这样设计、GC 为什么这样回收"的入口；届时本阶段的逃逸分析会升级为"看 SSA 优化管线"，sync.Pool 的 per-P 设计会追溯到调度器的 P 结构。在此之前可先按推荐学习顺序巩固 ph12 云原生与本阶段的练习与项目。

---

*本文全部"已验证"声明（go1.25.6 实测：示例 1~6、练习 1~4、项目全部命令与数字）均属实；`go tool trace` 浏览器 UI 与 `go tool pprof -http` 交互式界面属图形查看器，本环境只验证了命令行版与文件生成，标注「未在本环境验证」，不虚构验证。*
