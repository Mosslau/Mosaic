# ph16 PGO 与高级性能优化示例

> 五个示例覆盖本阶段全部"可运行"知识点：CPU profile 双路径采集（ex01-profserver）→ PGO 构建对比（ex02-pgo-build）→ pprof 热点下钻（ex03-pprof-analyze）→ 内存布局与分配优化前后对比（ex04-alloc-opt）→ 性能回归基线脚本（ex05-bench-baseline）。全部为完整可运行 Go module，零第三方依赖，在 go1.25.6（darwin/arm64）实测通过（`go vet`、`go test` 全绿；ex05 另含 bash 回归脚本实测）。所有 profile 与二进制产物一律写 /tmp，不进仓库。

| 示例 | 一句话说明 | 运行命令（进入各自子目录） |
|------|-----------|--------------------------|
| ex01-profserver | CPU profile 双路径采集：常驻服务用 net/http/pprof 边压测边采；批处理用 runtime/pprof 包揽一段代码 | `go test ./...`；`go build -o /tmp/ph16/ex01 .` 后按 main.go 文件头两路径运行 |
| ex02-pgo-build | PGO 构建对比：采集代表性 profile → `-pgo` 构建 → `go version -m` 印章 + 自计时对比（去虚拟化实测 3.5×） | 按 main.go 文件头 5 步运行 |
| ex03-pprof-analyze | 热点路径识别三件套：`go tool pprof` 的 top（谁最热）→ peek（调用上下文）→ list（行级热点） | 按 main.go 文件头 4 步运行 |
| ex04-alloc-opt | 内存布局与分配优化前后对比：Sprintf/+= vs Builder/strconv；结构体字段排序省 padding | `go test -run='^$' -bench=. -benchmem -count=5`；`go run .` |
| ex05-bench-baseline | 性能回归基线脚本（benchstat 思路）：中位数基线 + 阈值回归检查，exit 码可挂 CI | `./benchregress.sh baseline` → `./benchregress.sh check` → `SLOW=1 ./benchregress.sh check` |

## 实测记录（go1.25.6 darwin/arm64，Apple M4 Pro，2026-09-03）

数字随机器与 Go 版本波动 ±10~20%，以本机重跑为准；本表全部为本环境实测输出。

### ex01：CPU profile 双路径实测

**路径 A（net/http/pprof）**：4 路并行 curl 持续压测 `/work?n=20000000` 期间，`curl 'http://127.0.0.1:18080/debug/pprof/profile?seconds=3'` 采 3 秒：

```text
flat  flat%   sum%
4.86s 82.51%  82.51%  main.hashChain (inline)   ← 业务热点（4 核合计 5.40s cum / 3s 窗口）
0.54s  9.17%  91.68%  runtime.asyncPreempt      ← 热循环被抢占检查的采样
0.45s  7.64%  99.32%  syscall.syscall           ← 每请求一次 socket 写
```

**路径 B（runtime/pprof）**：`-batch -n 40000000 -cpuprofile` 自采：

```text
60ms  100%   100%  main.hashChain (inline)
```

**结论**：两条路径产出同一份 pprof 格式文件、同一套分析命令；net/http/pprof 的关键是"**在压测期间**采"（本例第一版顺序 curl 压测时服务器大半在等，top 被 syscall 占据——profile 必须采在负载真正运行时）。

### ex02：PGO 构建对比实测（本阶段核心数字）

```text
$ /tmp/ph16/ex02-base      checksum=1216 elapsed=255.6ms ns/op=1.300   ← 基线
$ /tmp/ph16/ex02-pgo       checksum=1216 elapsed=70.5ms  ns/op=0.359   ← PGO：快约 3.5×
$ go version -m /tmp/ph16/ex02-pgo | grep -- '-pgo'
	build	-pgo=/tmp/ph16/ex02.pprof                ← PGO 印章（基线二进制无此行）
$ # default.pgo 约定：profile 放进 main 包目录并命名 default.pgo，免 -pgo 标志构建
$ go version -m /tmp/ph16/ex02-auto | grep -- '-pgo'
	build	-pgo=/tmp/ph16/ex02auto/default.pgo      ← auto 约定实测生效
$ go build -pgo=/tmp/ph16/ex02.pprof -gcflags='-m' . | grep main.go
	./main.go:82:13: PGO devirtualizing interface call m.Mix to (*LCG).Mix   ← 去虚拟化
	./main.go:82:13: inlining call to (*LCG).Mix                            ← 随后内联
```

**结论**：PGO 把 99% 流量的接口调用从 itab 间接跳转改写为"类型断言 + 直接调用 + 内联"，本例每次迭代省掉一次间接调用开销，总收益 3.5×。**两个前提缺一不可**：① profile 必须来自代表性负载（99% LCG 的流量形态）；② 迭代间无依赖链（第一版 `s = m.Mix(s)` 链式依赖实测 PGO 零收益——乘加延迟链才是瓶颈，调用开销被 CPU 乱序执行掩盖）。checksum 前后一致 = 优化不改语义。

### ex03：pprof 三件套实测

```text
$ go tool pprof -top -nodecount=3 ex03 ex03.pprof
520ms  91.23%  main.validateRow          ← 业务热点直接登顶
$ go tool pprof -peek='renderBody' ex03 ex03.pprof
cum 30ms | main.renderBody              ← flat≈0%，症状全在 callee
         | runtime.concatstring2 100%   ← += 拼接的真实代价帧
$ go tool pprof -list='validateRow' ex03 ex03.pprof
190ms  190ms  for k := 0; k < 100; k++ {
300ms  310ms      h ^= uint64(r[i]) + uint64(k)   ← 热点精确到行
```

**结论**：top 给"谁最热"、peek 给"谁调用它/它调用谁"（症状帧 → 病因函数）、list 给"热在哪一行"。**环境备注**：本机（darwin/arm64）对分配密集的单线程程序，CPU profile 会有大量采样落在 runtime.kevent/pthread_cond 帧上（空转线程被信号采样）——本例把分配压到 ~5% 以获得干净归因；多 goroutine 服务（ex01 路径 A）无此现象。

### ex04：分配与布局优化实测（-count=5 取中位数）

| 基准 | ns/op | B/op | allocs/op | 对比 |
|------|-------|------|-----------|------|
| FormatNaive（Sprintf+`+=`） | 1,704,325 | 22,907,866 | 3,547 | 基线 |
| FormatOpt（Builder+AppendInt） | 20,338 | 98,304 | 2 | **快 84×、内存省 233×、分配 3547→2** |
| LayoutBad（字段乱序 40B） | 822,069 | 4,005,898 | 1 | 基线 |
| LayoutGood（按对齐排序 32B） | 327,155 | 3,203,077 | 1 | **省 20% 内存、遍历快 2.5×** |

**结论**：`fmt.Sprintf` 每事件 ~3.5 次分配（装箱 + 中间串），`strconv.Itoa` 也会分配（换 `AppendInt`+栈上 scratch 才归零）；结构体字段按对齐降序排列，10 万元素省 800KB——**B/op 就是结构体尺寸 × 元素数的直接证据**。正确性由 `TestFormatEquivalence` 保证两版输出逐字节一致。

### ex05：回归基线脚本实测

```text
$ ./benchregress.sh baseline      → 基线中位数 27.65 ns/op 写入 /tmp
$ ./benchregress.sh check         → PASS   27.6 → 27.2 ns/op（-1.6%）   exit 0
$ SLOW=1 ./benchregress.sh check  → REGRESSION 27.6 → 103.5 ns/op（+274.5%） exit 1
$ benchstat baseline.txt current.txt → +278.39% (p=0.002 n=6)   ← 统计显著
```

**结论**：中位数 + 阈值是最小可用的回归闸门（零依赖，bash+awk 即可）；benchstat 额外给出 p 值做统计显著性判断（`go install golang.org/x/perf/cmd/benchstat@latest`——注意它要求 go ≥ 1.26 构建自身，本环境实测通过 GOTOOLCHAIN 自动下载 go1.26.8 完成安装）。阈值不要定太小：同机波动就有 ±10~20%。

## 验证说明

- 全部示例 `go vet ./...`、`go test ./...` 通过（ex01/ex03/ex04/ex05 含单测；ex02 为构建对比演示，正确性由 checksum 前后一致保证）
- 实测环境：go1.25.6 darwin/arm64，Apple M4 Pro；GOCACHE/GOMODCACHE 重定位到 /tmp；零第三方依赖，可离线复现
- profile 与二进制产物一律写 /tmp（`git status` 无产物）；ex02 的 default.pgo auto 约定在 /tmp 副本上验证，仓库目录不留 profile 文件
