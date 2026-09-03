// 来源：ph16-pgo-advanced-perf 练习 2 参考实现（sol-02-pgo-build，用 PGO 构建服务）
// 一句话说明：一个命令分发服务内核——95% 流量走 process 命令、5% 走 audit，
// 命令处理器以接口注入（真实服务的典型形态）。完整走 PGO 四步：
// 采集代表性 profile → -pgo 构建 → `go version -m` 验证印章 → 自计时对比。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd sol-02-pgo-build；产物一律 /tmp）：
//
//	# 1. 基线构建 + 自计时
//	go build -o /tmp/ph16/sol02-base . && /tmp/ph16/sol02-base
//	# 2. 采集代表性负载的 CPU profile
//	go build -o /tmp/ph16/sol02-prof . && /tmp/ph16/sol02-prof -cpuprofile /tmp/ph16/sol02.pprof
//	# 3. PGO 构建并验证印章
//	go build -pgo=/tmp/ph16/sol02.pprof -o /tmp/ph16/sol02-pgo .
//	go version -m /tmp/ph16/sol02-pgo | grep -- '-pgo'
//	# 4. 对比
//	/tmp/ph16/sol02-pgo
//
// 验证块（go1.25.6 实测，2026-09-02，数字随机器波动 ±10~20%）：
//
//	$ /tmp/ph16/sol02-base   → checksum=4480 elapsed=97.8ms ns/op=0.746
//	$ /tmp/ph16/sol02-pgo    → checksum=4480 elapsed=48.6ms ns/op=0.371（快约 2.0×）
//	$ go version -m /tmp/ph16/sol02-pgo | grep -- '-pgo'
//		build	-pgo=/tmp/ph16/sol02.pprof
//	$ go build -pgo=... -gcflags='-m' . | grep devirt
//		./main.go:82:16: PGO devirtualizing interface call h.Handle to (*processHandler).Handle
//	checksum 前后一致 = PGO 不改语义只改性能
//	（serve 不加 //go:noinline 时本机实测 PGO 无收益——原因见 serve 前的注释，
//	 该"去虚拟化决策打出但收益消失"的对照也是本示例的实测教学点之一）
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"runtime/pprof"
	"time"
)

// Handler 是命令处理器接口：真实服务里 handler 以接口注入（可替换、可 mock），
// 代价是每次调用走 itab 间接跳转——PGO 去虚拟化要消除的正是这个成本。
type Handler interface {
	Handle(uint64) uint64
}

// processHandler 占 95% 流量：乘加混合（体积极小，调用开销占比高）。
// 带配置字段（A/C）是刻意的：间接调用会阻止编译器把字段加载提升出循环——
// 这正是去虚拟化+内联之后才能解锁的收益（对照：零字段版本在本机实测几乎无收益，
// 因为 Apple silicon 上预测命中的间接调用本身就很便宜）。
type processHandler struct {
	A uint64
	C uint64
}

func (h *processHandler) Handle(x uint64) uint64 { return x*h.A + h.C }

// auditHandler 占 5% 流量：异或折叠。它的存在让分发保持接口形态。
type auditHandler struct{}

func (*auditHandler) Handle(x uint64) uint64 {
	x ^= x >> 33
	x *= 0xff51afd7ed558ccd
	return x ^ (x >> 29)
}

// serve 是分发热点：对一批相互独立的请求逐一调用接口方法。
// 调用点 h.Handle(v) 的 profile 会记录 95% processHandler——PGO 据此插入类型断言。
//
// //go:noinline 是本示例的实测关键：go1.25 的内联器会把这个小函数连循环一起
// 内联进 main（-m 打印 inlining call to serve），此时 PGO 的去虚拟化守卫与
// A/C 字段提升落在外层复杂循环（含 map 查表、r%20 分支）上无法完整生效——
// 本机实测该形态下 PGO 无收益（0.77 vs 0.85 ns/op，波动内）。
// 保持 serve 为独立函数后，PGO 在 serve 内部完成"类型守卫 + 直接调用 + 内联 +
// 字段提升"整套变换，收益稳定 ~2×（0.76 → 0.38 ns/op）。
// 教学点：PGO 的收益发生在函数内层循环上；热函数被"过度内联"后优化反而可能失焦。
//
//go:noinline
func serve(h Handler, in []uint64) uint64 {
	var s uint64
	for _, v := range in {
		s ^= h.Handle(v) // 热点调用点：PGO 在这里去虚拟化 + 内联
	}
	return s
}

func main() {
	rounds := flag.Int("r", 2000, "轮数（每轮处理 65536 个请求）")
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

	in := make([]uint64, 1<<16)
	rng := rand.New(rand.NewPCG(42, 0))
	for i := range in {
		in[i] = rng.Uint64()
	}

	// 代表性流量：95% process + 5% audit
	handlers := map[string]Handler{
		"process": &processHandler{A: 6364136223846793005, C: 1442695040888963407},
		"audit":   &auditHandler{},
	}
	start := time.Now()
	var s uint64
	for r := 0; r < *rounds; r++ {
		h := handlers["process"]
		if r%20 == 0 {
			h = handlers["audit"]
		}
		s ^= serve(h, in) + uint64(r)
	}
	el := time.Since(start)
	total := float64(*rounds) * float64(1<<16)
	fmt.Printf("checksum=%d elapsed=%s ns/op=%.3f\n", s, el, float64(el.Nanoseconds())/total)
}
