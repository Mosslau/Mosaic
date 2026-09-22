# ph14 阶段项目：Go runtime 机制实验台（rtlab）

## 需求

对应 roadmap ph14「推荐项目」之「Go runtime 机制实验笔记」。本阶段学的是 Go 底层机制（GMP 调度、GC 触发、slice/map/channel/interface 内部结构、defer/panic 语义），但这些机制大多是**黑盒**——本项目把它们变成**可观测的实验**：不碰 runtime 内部结构，只用公开 API（`cap`、`runtime.NumGoroutine`、`runtime.ReadMemStats`、channel 行为、`debug.SetGCPercent`）把底层机制"逼"出来，产出一份可复现的实验报告。五个实验包：

| 实验包 | 观测什么 | 用哪些公开 API |
|--------|---------|---------------|
| `internal/slicegrow` | slice 扩容步长：<256 翻倍、≥256 约 1.25 倍 + size class 取整 | `cap`（反复 append 记录成长点） |
| `internal/deferx` | defer LIFO、参数求值、命名返回值、recover 范围、嵌套 panic、panic(nil) | 纯函数 + `recover` |
| `internal/gmp` | GMP 可观测面：GOMAXPROCS=核数、goroutine 创建/汇合计数（泄漏检测） | `runtime.GOMAXPROCS/NumCPU/NumGoroutine`、`Gosched` |
| `internal/gcstats` | GC 不是定时器：GOGC=100 vs -1 下同一分配压力的 GC 次数与暂停 | `runtime.ReadMemStats`（NumGC/PauseTotalNs）、`debug.SetGCPercent` |
| `internal/chanx` | channel 语义：无缓冲同步、缓冲解耦、关闭读零值、select 随机、并发安全 | channel 原生行为 + `sync.WaitGroup` |

## 功能清单

- [x] `cmd/rtlab` CLI：`-exp slice|defer|gmp|gc|chan|all` 单独或一键跑实验
- [x] 五个实验包各产出可复现报告（`Report()` 纯函数，供 CLI 与测试共用）
- [x] 每个实验包配测试：断言**结构性语义**（扩容规则、defer 顺序、GC 对比、channel 语义、无泄漏）
- [x] 全量验证：`go test ./...`、`go vet ./...`、`go test -race ./...` 通过

## 运行方式（已在 go1.25.6 / darwin / arm64 验证，零第三方依赖）

```bash
cd languages/go/ph14-advanced-go/project
go test ./... && go test -race ./...          # 验证：测试 + 竞态检测
go run ./cmd/rtlab -exp all                   # 一键跑全部实验
go run ./cmd/rtlab -exp slice                 # 单独跑某个实验
go run ./cmd/rtlab -exp gc
```

## 验收标准

- [ ] **五个实验全部有可复现输出**：`go run ./cmd/rtlab -exp all` 输出五段报告（见下方实测记录），数字随机器/Go 版本波动但趋势稳定
- [ ] **测试断言的是语义不是巧合**：扩容测试断言规则（翻倍/1.25 倍）而非具体数字；gmp 泄漏断言用"差 <10"而非精确相等（NumGoroutine 含运行时后台 goroutine 抖动）；GC 测试用比较式断言（GOGC=100 次数 > GOGC=-1）
- [ ] **`go test -race ./...` 通过**：chanx 的并发计数与 gmp 的并发汇合零数据竞争
- [ ] **能解释每个实验对应哪个底层机制**：见主文档第 4 章（slice 描述符、Swiss map、iface、hchan、GMP、GC）

## 实测记录（go1.25.6，Apple M4 Pro，2026-09-01）

**`go run ./cmd/rtlab -exp all` 完整输出**：

```
== [slice] slice 扩容步长实测（cap 成长点序列）==
[]int     : [1 2 4 8 16 32 64 128 256 512 848 1280 1792 2560]
[]byte    : [1 8 16 32 64 128 256 512 896 1408 2048]
[][32]byte: [1 2 4 8 16 32 64 128 256 512 852 1280 1792 2560]

== [defer] defer / panic-recover 语义实测 ==
order       : [body defer3 defer2 defer1]
arg-eval    : body=100 captured=1（参数在 defer 语句处求值）
closure     : 100（闭包引用看最终值）
named-return: 50（return 5 后 defer ×10）
recover     : boom（只在 defer 内生效）
nested      : inner（内层 panic 覆盖外层）
panic(nil)  : nil? false, *runtime.PanicNilError（Go 1.21+ 起非 nil）
safe-call   : panic recovered: x

== [gmp] GMP 调度模型可观测面 ==
GOMAXPROCS=14 NumCPU=14（P 数 = 核数，M 数运行时内部管理、外部不可见）
初始 goroutine 数=1
8 个 goroutine 让出 P 并汇合后=1（初始 1 → 回到初始值 = 无泄漏）

== [gc] GOGC 与 GC 触发次数 ==
GOGC=100（默认，堆翻倍触发）: 压力期间 GC 6 次, 累计暂停 57.209µs
GOGC=-1 （关闭自动 GC）  : 压力期间 GC 0 次, 累计暂停 0s

== [chan] channel 底层语义 ==
无缓冲同步  : 发送耗时 292ns, 完成=true（接收方先就绪则发送立即配对）
缓冲不阻塞  : 容量 3 吸收 3 次发送，drop=0
关闭读零值  : 见测试断言（v/ok/range 三态）
select 随机 : 100 次选择 → a=60 b=40（两分支都被选中，非固定优先级）
并发安全计数: ConcurrentSafeCounter(1000) = 1000（channel 内部同步，-race 零报告）
```

**结论解读**（对应主文档第 4 章）：

- **slice**：cap<256 翻倍、≥256 约 1.25 倍后按 size class 取整（int 512→848、byte 512→896、[32]byte 512→852）；`[]byte` 首轮 1→8 是分配器最小块抬升——扩容规则一致、取整结果随元素大小变
- **defer**：LIFO、参数即求值、闭包看最终值、defer 可改命名返回值、recover 只在 defer 内生效、内层 panic 覆盖外层、Go 1.21+ panic(nil) recover 非 nil——七条语义全部实测
- **GMP**：P 数 = GOMAXPROCS = NumCPU（本机 14）；goroutine 汇合后计数回落（无泄漏）；M 在运行时内部管理、外部不可见——"黑盒观测"只能看到这三个数
- **GC**：同一压力下 GOGC=100 触发 6 次 GC（累计暂停 57µs），GOGC=-1 一次都不触发——GC 是"堆增长到阈值触发"，不是定时器
- **channel**：无缓冲 = 同步点（发送 292ns 完成，因接收方已就绪）；缓冲 = 解耦；关闭 = 广播（读零值）；select 随机（60/40）；channel 内部自带同步（1000 并发计数精确、-race 零报告，对照 ex02 的 map 并发写 fatal）

## 扩展方向（可选）

- 加 `-exp map`：用 ex02 的思路把 map 并发写 fatal 做成受控实验（`go test` 之外的独立子进程跑）
- 用 `runtime/metrics` 或 `runtime/trace` 给 gmp 实验加调度时间线（衔接 ph13 的 trace 方法）
- 给 slicegrow 加基准：预分配 vs 自然扩容的 allocs 对比（衔接 ph13 的 -benchmem）
- 加 `-json` 输出：实验报告序列化成 JSON，便于自动化回归对比（衔接 ph08 测试与 CI）
