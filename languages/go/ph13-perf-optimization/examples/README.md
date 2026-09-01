# ph13 性能优化 示例

> 六个示例覆盖本阶段全部知识点：benchmark 量化（ex01）→ 逃逸分析（ex02）→ pprof 定位（ex03）→ sync.Pool 复用（ex04）→ 锁竞争与 profile（ex05）→ goroutine 泄漏与 trace（ex06）。全部为完整可运行 Go module，零第三方依赖，在 go1.25.6（darwin/arm64）实测通过（`go vet`、`go test`、`go test -race` 全绿）。

| 示例 | 一句话说明 | 运行命令（进入各自子目录） |
|------|-----------|--------------------------|
| ex01-benchmark | 字符串拼接三写法与 slice 预分配：读 ns/op / B/op / allocs/op 三列指标 | `go test -v ./...`；`go test -run='^$' -bench=. -benchmem -benchtime=2000x` |
| ex02-escape-analysis | 逃逸分析：`-gcflags='-m'` 打印裁决，堆 vs 栈的基准对照 | `go test -v ./...`；`go build -gcflags='-m' .`；`go test -run='^$' -bench=. -benchmem -benchtime=1000000x` |
| ex03-pprof-cpu-mem | runtime/pprof 采集 CPU 与 heap profile，`go tool pprof -top` 定位热点 | `go build -o /tmp/ex03 .`；`/tmp/ex03 -cpuprofile=/tmp/cpu.pprof`；`go tool pprof -top -nodecount=3 /tmp/ex03 /tmp/cpu.pprof`（mem 同理） |
| ex04-sync-pool | sync.Pool 复用临时缓冲：Get→Reset→Put 三要素、GC 清池、小负载边界 | `go test -v ./...`；`go test -race ./...`；`go test -run='^$' -bench=. -benchmem -benchtime=100000x` |
| ex05-lock-contention | 三种同步策略（全局锁/分片/atomic）+ mutex/block profile 定位等待点 | `go test -v ./...`；`go test -race ./...`；`go test -run='^$' -bench=. -benchtime=1s -cpu=8`；`go run .` |
| ex06-goroutine-leak-trace | 无缓冲 channel 发送方泄漏：NumGoroutine 计数 + goroutine profile 定位 + 缓冲修复 + trace 采集 | `go test -v ./...`；`go test -race ./...`；`go run .` |

## 实测记录（go1.25.6，Apple M4 Pro，2026-09-01）

数字随机器波动，以本机重跑为准；本表全部为本环境实测输出。

### ex01：benchmark 三列指标（1000 次迭代/op，-benchtime=2000x）

| 基准 | ns/op | B/op | allocs/op |
|------|-------|------|-----------|
| ConcatPlus（`+=` 拼接） | 74947 | 530281 | 999 |
| ConcatBuilder（`strings.Builder` + Grow） | 1975 | 1024 | 1 |
| ConcatJoin（`strings.Join`） | 6701 | 1024 | 1 |
| AppendNoPrealloc（append 自然扩容） | 2479 | 25208 | 12 |
| AppendPrealloc（make 预分配容量） | 781.9 | 8192 | 1 |

**结论**：`+=` 是 O(n²) 且每轮分配（999 allocs）；Builder 快 38 倍、Join 快 11 倍且都是 1 alloc。slice 预分配省 11 次分配、快 3.2 倍。allocs/op 是 GC 压力的源头——本阶段所有优化都以这三列收尾。

### ex02：逃逸分析裁决（go build -gcflags='-m' 实测输出节选）

```
./main.go:36:2: moved to heap: p          ← makePoint：返回局部变量地址 → 堆（1 allocs/op）
./main.go:52:6: moved to heap: b          ← bigBuf：1 MiB 对象太大，栈放不下
./main.go:59:17: len(s) escapes to heap   ← printLen：len(s) 装箱进 interface{} 参数
```

| 基准 | ns/op | B/op | allocs/op |
|------|-------|------|-----------|
| BenchmarkEscaped（makePoint 返回指针） | 9.13 | 16 | 1 |
| BenchmarkStack（makePointVal 按值返回） | 0.80 | 0 | 0 |

**结论**：同一份数据，按值返回留栈（0 allocs、快约 11 倍）；返回地址必逃逸。注意逃逸裁决是「调用上下文相关」的——main 里 `makePointVal()` 传给 `fmt.Println` 时同样会逃逸（`-m` 输出可见）。

### ex03：pprof -top 实测（故意构造的 CPU 与堆热点）

```
CPU profile（Total samples = 1.10s）:
      flat  flat%   sum%   cum   cum%
     1.03s 93.64% 93.64%  1.03s 93.64%  main.fib          ← 递归热点占绝对主导
     0.04s  3.64% 97.27%  0.04s  3.64%  runtime.pthread_cond_signal

heap inuse_space（Total = 5125.57kB）:
  3074.82kB 59.99% 59.99% 3587.32kB 69.99%  main.makeGarbage  ← 堆分配热点
    1026kB 20.02% 80.01%   1026kB 20.02%  runtime.allocm
```

**结论**：CPU profile 回答「时间花在哪个函数」（fib 93.6%），heap profile 回答「内存在哪里分配」（makeGarbage 60%）。`-top -nodecount=3` 只看前三名；完整交互式分析用 `go tool pprof -http`（未在本环境验证浏览器 UI）。CPU 采样是 100Hz 的，程序跑太短会采不到样本（Total samples = 0）——本示例的 cpuWork 特意跑满约 1 秒。

### ex04：sync.Pool 实测与边界（并发 RunParallel，-benchtime=100000x）

| 场景 | 朴素版（每次新建 Buffer） | Pool 版 | 差异 |
|------|--------------------------|---------|------|
| 大负载（4090 B） | 821.0 ns/op，4096 B，1 allocs | 16.32 ns/op，0 B，0 allocs | Pool 快约 50 倍 |
| 小负载（约 50 B） | 32.67 ns/op，64 B，1 allocs | 5.09 ns/op，0 B，0 allocs | Pool 快约 6.4 倍 |

**sync.Pool 什么时候值得用（边界实测）**：上面两行里朴素版每次都逃逸分配（64 B 或 4096 B），Pool 稳赢。但若对象**能完全留在栈上**（如固定小数组，零分配），情况反转——实测（附加实验，非本示例代码）：

| 基准（单线程） | ns/op | allocs/op |
|----------------|-------|-----------|
| 栈数组版（零分配） | 2.37 | 0 |
| Pool 版（Get/Put 簿记） | 8.28 | 0 |

栈版快约 3.5 倍——**Pool 的 Get/Put 簿记是纯开销，省不掉的对象才值得 Pool**。正确判断顺序：① 对象能留栈吗（逃逸分析）？能 → 别用 Pool，直接用栈变量；② 不能留栈且创建频繁、分配大 → Pool 摊销分配成本；③ 小对象且低频 → 不值得。另外 Pool 会被 GC 清空（只存临时对象）、Get 后必须 Reset（池里对象是脏的）、对象生命周期必须「用完可弃」（不能长期持有引用）。

### ex05：锁竞争实测（-benchtime=1s 时长基准，-cpu=8，RunParallel）

| 基准 | ns/op | 相对全局锁 |
|------|-------|-----------|
| GlobalCounter（全局互斥锁） | ~95.2 | 1x |
| ShardedCounter（16 分片锁 + 缓存行 padding） | ~61.4 | 快 1.5 倍 |
| AtomicCounter（atomic.AddInt64） | ~34.9 | 快 2.7 倍 |

**mutex profile 实测（go run . 输出节选）**：`DemoMutexContention.func1` 在 `main.go:99`（`mu.Lock()`）与 `main.go:100`（`mu.Unlock()`）处被聚出大量等待事件——profile 精确告诉你「等在哪一行」。

**block profile 实测（节选）**：`--- contention:` 下栈为 `runtime.chanrecv1` → `main.DemoBlockProfile`（`main.go:125`，`<-ch` 阻塞点），等待约 2100 万 cycles。

**结论**：① 分片把竞争摊薄（8 goroutine 抢 1 把锁 → 每片平均 0.5 个），但若操作本身重（如 map 写），分片收益会被操作成本淹没（见练习 sol-04 的实测讨论）；② atomic 无锁无挂起，竞争激烈时通常最快，但多字段复合状态锁不了，且高竞争下同一缓存行乒乓可能反超分片锁；③ 优化前先 `SetMutexProfileFraction` + mutex profile 确认「锁是不是瓶颈」。

### ex06：goroutine 泄漏实测（go run . 输出节选）

```
goroutines before: 1
goroutines after 20 leaky calls: 21        ← 20 次超时调用泄漏 20 个 goroutine
goroutine profile: total 21
20 @ ... main.leakySend.func1 ... main.go:31   ← 泄漏栈聚在 ch <- work()
trace 已写入 /tmp/ex06-trace.out（4701 字节）
```

**结论**：泄漏的检测三步——`runtime.NumGoroutine` 看数量、goroutine profile 看栈、修复后重测数量回落；修复是缓冲 1 或 context 取消（ph06）。execution trace（`runtime/trace`）记录调度与阻塞事件，`go tool trace` 浏览器 UI 属交互式查看器，未在本环境验证。

## 验证说明

- 全部示例 `go vet ./...`、`go test ./...`、`go test -race ./...` 通过（ex04/ex05/ex06 含并发测试，-race 零数据竞争）
- 本表实测环境：go1.25.6 darwin/arm64，Apple M4 Pro；机器差异会导致数字波动，趋势（哪个快、哪个省分配）稳定
- `go tool trace` 浏览器 UI、`go tool pprof -http` 交互式界面未在本环境验证，命令行版 `-top` 已实测
