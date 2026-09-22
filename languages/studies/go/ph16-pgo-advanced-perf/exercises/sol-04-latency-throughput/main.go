// 来源：ph16-pgo-advanced-perf 练习 4 参考实现（sol-04-latency-throughput，优化前后延迟与吞吐对比）
// 一句话说明：一个"哈希网关"模拟器——N 个请求、每个请求负载大小伪随机（256B~4KB）、
// 逐字节走 Codec 接口分派（90% mulCodec / 10% xorCodec，真实服务里"算法可插拔"的形态）。
// 逐请求计时 → 报 p50/p95/p99/均值延迟与吞吐（req/s）；分别构建基线与 -pgo 二进制跑同一负载，
// 对比"优化前后延迟和吞吐"（roadmap §16 练习 3 的落地）。正确性由 digest 前后一致保证。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd sol-04-latency-throughput；产物一律 /tmp）：
//
//	# 1. 测试 + 构建基线
//	go test ./... && go vet ./... && go build -o /tmp/ph16/sol04-base .
//	# 2. 基线报告（逐请求计时：延迟分位数 + 吞吐）
//	/tmp/ph16/sol04-base
//	# 3. 采集代表性 profile + PGO 构建 + 印章验证
//	#    （-cpuprofile 模式跳过逐请求计时只跑同一批请求的纯计算——原因见 main 内注释，
//	#     本机实测逐请求 time.Now 会把 CPU 采样偏置到 main.main，PGO 权重失真）
//	go build -o /tmp/ph16/sol04-prof . && /tmp/ph16/sol04-prof -cpuprofile /tmp/ph16/sol04.pprof
//	go build -pgo=/tmp/ph16/sol04.pprof -o /tmp/ph16/sol04-pgo .
//	go version -m /tmp/ph16/sol04-pgo | grep -- '-pgo'
//	# 4. PGO 报告（同一负载、同一机器，与基线逐请求计时口径完全一致）
//	/tmp/ph16/sol04-pgo
//
// 验证块（go1.25.6 实测，2026-09-02，n=200000，数字随机器波动 ±10~20%，方向稳定）：
//
//	$ /tmp/ph16/sol04-base   → p50=1.625µs p95=2.96µs p99=3.25µs  吞吐 ≈590k req/s  digest=687c9e21f5b4886c
//	$ /tmp/ph16/sol04-pgo    → p50=0.917µs p95=2.21µs p99=3.75µs  吞吐 ≈955k req/s  digest=687c9e21f5b4886c
//	                          p50 快约 1.8×、吞吐高约 1.6×（PGO 去虚拟化到 (*mulCodec).Mix，
//	                          决策行：PGO devirtualizing interface call c.Mix to (*mulCodec).Mix）
//	                          注：p99 3.25→3.75µs 微升属尾部离群/负载分布效应（±10~20%
//	                          波动内），主要收益在 p50 与吞吐——不误读为"PGO 变差"
//	digest 相同 = 优化只改性能不改语义；单次运行有 ±10~20% 抖动（本机一次基线 448k req/s
//	的离群来自系统负载），对比结论取多次运行的方向与量级
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
	"sort"
	"time"
)

// Codec 是逐字节哈希算法接口：真实服务里算法可插拔（A/B 试验、按数据特征选算法），
// 代价是每次调用走 itab 间接跳转——PGO 去虚拟化要消除的正是这个成本。
type Codec interface {
	Mix(uint64) uint64
}

// mulCodec 占 90% 流量：乘加混合。带配置字段（A/C）是刻意的——间接调用阻止编译器
// 把字段加载提升出循环，去虚拟化 + 内联之后这个提升才解锁（同 ex02/sol-02 的机制）。
type mulCodec struct {
	A uint64
	C uint64
}

func (m *mulCodec) Mix(x uint64) uint64 { return x*m.A + m.C }

// xorCodec 占 10% 流量：异或折叠。它的存在让调用点保持接口形态。
type xorCodec struct{}

func (*xorCodec) Mix(x uint64) uint64 {
	x ^= x >> 33
	x *= 0xff51afd7ed558ccd
	return x ^ (x >> 29)
}

// digest 处理一个请求：对 size 字节逐字节调用 c.Mix（每字节独立，结果异或折叠）。
// 输入相互独立（h ^= … 而非 h = c.Mix(h)），乘加延迟可被 CPU 流水线隐藏，
// 每字节的"调用开销"才暴露在关键路径上——这正是 PGO 收益的形态（见 examples/ex02）。
//
// //go:noinline 是本示例的实测关键（同 sol-02 的 serve）：digest 若被内联进 main，
// PGO 去虚拟化收益消失；保持为独立函数后，去虚拟化 + 字段提升在内层循环上完整生效。
//
//go:noinline
func digest(c Codec, size int, seed uint64) uint64 {
	var h uint64
	for i := 0; i < size; i++ {
		h ^= c.Mix(uint64(byte(seed+uint64(i))) + 1) // 热点调用点：PGO 在这里去虚拟化
	}
	return h
}

// pickCodec 模拟流量构成：90% mulCodec、10% xorCodec（与请求序号确定性绑定，可复现）。
func pickCodec(r int, mul *mulCodec, xor *xorCodec) Codec {
	if r%10 == 9 {
		return xor
	}
	return mul
}

// requestSize 确定性伪随机请求大小：256B ~ 4KB，让延迟有分布（p50 < p95 < p99 才有意义）。
func requestSize(r int) int {
	return 256 + (r*1103515245>>16)%(4096-256)
}

func main() {
	n := flag.Int("n", 200000, "请求数")
	prof := flag.String("cpuprofile", "", "非空则采集 CPU profile 到该文件")
	flag.Parse()

	if *prof != "" {
		f, err := os.Create(*prof)
		if err != nil {
			fmt.Fprintln(os.Stderr, "创建 profile 文件失败:", err)
			os.Exit(1)
		}
		if err := pprof.StartCPUProfile(f); err != nil {
			fmt.Fprintln(os.Stderr, "启动 CPU profile 失败:", err)
			os.Exit(1)
		}
		defer func() {
			pprof.StopCPUProfile()
			f.Close()
		}()
	}

	mul := &mulCodec{A: 6364136223846793005, C: 1442695040888963407}
	xor := &xorCodec{}

	// measure=false（-cpuprofile 模式）：跳过逐请求计时，只跑同一批请求的纯计算。
	// 为什么：本机（darwin/arm64）实测，逐请求 time.Now 会把 CPU profile 的采样
	// 严重偏置到 main.main（90%+ 采样落空，digest/Mix 帧几乎采不到）——PGO 拿到
	// 失真的权重后甚至会选错去虚拟化目标（选到 10% 的 xorCodec，实测反而变慢）。
	// 去掉计时后同一负载的 profile 干净（digest+mulCodec 占 ~9 成），PGO 决策正确。
	// 教学点：profile 的"采集形态"必须等于你想要的"优化形态"，这是代表性负载的一层含义。
	measure := *prof == ""

	lats := make([]float64, 0, *n) // µs
	var digestSum uint64
	start := time.Now()
	for r := 0; r < *n; r++ {
		size := requestSize(r)
		c := pickCodec(r, mul, xor)
		if measure {
			t0 := time.Now()
			digestSum ^= digest(c, size, uint64(r))
			lats = append(lats, float64(time.Since(t0).Nanoseconds())/1000.0)
		} else {
			digestSum ^= digest(c, size, uint64(r))
		}
	}
	wall := time.Since(start)

	if !measure {
		fmt.Printf("requests=%d wall=%s digest=%x\n", *n, wall.Round(time.Millisecond), digestSum)
		return
	}

	sort.Float64s(lats)
	per := func(q float64) float64 { return lats[int(q*float64(len(lats)))-1] }
	var sum float64
	for _, l := range lats {
		sum += l
	}
	fmt.Printf("requests=%d wall=%s throughput=%.0f req/s digest=%x\n",
		*n, wall.Round(time.Millisecond), float64(*n)/wall.Seconds(), digestSum)
	fmt.Printf("latency(µs): p50=%.3f p95=%.3f p99=%.3f mean=%.3f\n",
		per(0.50), per(0.95), per(0.99), sum/float64(len(lats)))
}
