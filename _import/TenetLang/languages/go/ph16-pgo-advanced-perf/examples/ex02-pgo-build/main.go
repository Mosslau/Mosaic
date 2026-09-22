// 来源：ph16-pgo-advanced-perf 示例 ex02-pgo-build（PGO 构建对比）
// 一句话说明：一个"热接口调用"工作负载——99% 的调用走同一个具体类型（LCG），
// 演示 PGO 的去虚拟化（devirtualization）带来的可测量收益：
// 先用代表性负载采集 CPU profile，再分别构建基线与 -pgo 二进制，
// 用 `go version -m` 的 -pgo 印章证实 PGO 生效，用自计时 ns/op 对比两者。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd ex02-pgo-build；构建产物与 profile 一律放 /tmp）：
//
//	# 1. 基线构建 + 自计时
//	go build -o /tmp/ph16/ex02-base . && /tmp/ph16/ex02-base
//	# 2. 采集代表性 profile（同一代码路径、同一负载形态）
//	go build -o /tmp/ph16/ex02-prof . && /tmp/ph16/ex02-prof -cpuprofile /tmp/ph16/ex02.pprof
//	# 3. PGO 构建（显式指定 profile；若命名为 default.pgo 放本目录则 -pgo=auto 自动采用）
//	go build -pgo=/tmp/ph16/ex02.pprof -o /tmp/ph16/ex02-pgo .
//	# 4. 验证 PGO 印章 + 对比自计时
//	go version -m /tmp/ph16/ex02-pgo | grep -- '-pgo'
//	/tmp/ph16/ex02-pgo
//	# 5. 看编译器决策差异：PGO 构建多出去虚拟化 + 内联两行
//	go build -gcflags='-m' . 2>&1 | grep -i 'mix\|process'
//	go build -pgo=/tmp/ph16/ex02.pprof -gcflags='-m' . 2>&1 | grep -i 'devirt\|inlining call to (\*LCG)'
//
// 验证块（go1.25.6 实测，2026-09-03，数字随机器波动 ±10~20%，但 3 倍量级稳定复现）：
//
//	$ /tmp/ph16/ex02-base    → checksum=1216 elapsed=255.6ms ns/op=1.300
//	$ /tmp/ph16/ex02-pgo     → checksum=1216 elapsed=70.5ms  ns/op=0.359（快约 3.5×）
//	$ go version -m /tmp/ph16/ex02-pgo | grep -- '-pgo'
//		build	-pgo=/tmp/ph16/ex02.pprof          ← PGO 印章：构建时采纳了 profile
//	（基线二进制同命令无此行；把 profile 命名为 default.pgo 放进 main 包目录后
//	 免 -pgo 标志构建，印章自动变为 -pgo=<目录>/default.pgo——auto 约定实测生效）
//	"checksum 相同" = 两次构建数学结果一致，优化只改性能不改语义
//	$ go build -pgo=... -gcflags='-m' . 多出两行关键决策（基线构建没有）：
//		./main.go:82:13: PGO devirtualizing interface call m.Mix to (*LCG).Mix
//		./main.go:82:13: inlining call to (*LCG).Mix
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"runtime/pprof"
	"time"
)

// Mixer 是热路径上的接口：调用方只持有接口值，编译期不知道具体类型，
// 普通构建下 Mix 调用走 itab 间接跳转（itab 布局见 ph14 高级 Go 阶段）。
// PGO 看到 profile 里该调用点 99% 是 *LCG 后，会插入类型断言分支，
// 把间接调用改写为直接调用（去虚拟化），直接调用随即被内联——
// 每次迭代省掉一次间接跳转 + call/ret 开销。
type Mixer interface {
	Mix(uint64) uint64
}

// LCG 是占 99% 流量的主流实现：纯整数乘加，函数体极小——
// 小到"调用本身的开销"比函数体还贵，正是去虚拟化收益最明显的形态。
type LCG struct {
	A uint64
	C uint64
}

func (m *LCG) Mix(x uint64) uint64 { return x*m.A + m.C }

// XorFold 是占 1% 流量的冷门实现，作用是让调用点保持"接口形态"——
// 如果只有一个实现且类型已知，编译器不需要 PGO 就能静态分派。
type XorFold struct{}

func (*XorFold) Mix(x uint64) uint64 {
	x ^= x >> 33
	x *= 0xff51afd7ed558ccd
	return x ^ (x >> 29)
}

// process 是 profile 里的热点帧：对一批相互独立的输入逐一调用接口方法。
// 输入相互独立（s ^= … 而非 s = m.Mix(s)）很关键：迭代间无依赖链，
// CPU 可以流水线并行，此时"每次迭代的调用开销"才真正暴露在关键路径上——
// 这也是 PGO 收益从"被依赖链掩盖"变成"3 倍"的原因（见 examples/README.md 实测）。
func process(m Mixer, in []uint64) uint64 {
	var s uint64
	for _, v := range in {
		s ^= m.Mix(v) // 热点调用点：PGO 在这里插入类型断言 + 直接调用 + 内联
	}
	return s
}

// run 模拟"代表性负载"：3000 轮中 99% 用 LCG、1% 用 XorFold。
// checksum 打印出来防止编译器把整个循环优化掉（ph13 的 sink 纪律），
// 同时充当"优化前后语义一致"的断言：基线与 PGO 二进制的 checksum 必须相同。
func run(rounds int) (uint64, time.Duration) {
	in := make([]uint64, 1<<16) // 64K 个输入 ≈ 512KB，驻留 L2 缓存
	rng := rand.New(rand.NewPCG(42, 0))
	for i := range in {
		in[i] = rng.Uint64()
	}

	lcg := &LCG{A: 6364136223846793005, C: 1442695040888963407}
	xf := &XorFold{}
	start := time.Now()
	var s uint64
	for r := 0; r < rounds; r++ {
		m := Mixer(lcg)
		if r%100 == 0 { // 1% 的冷门路径
			m = xf
		}
		s ^= process(m, in) + uint64(r)
	}
	return s, time.Since(start)
}

func main() {
	rounds := flag.Int("r", 3000, "轮数（每轮处理 65536 个独立输入）")
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

	s, el := run(*rounds)
	total := float64(*rounds) * float64(1<<16)
	fmt.Printf("checksum=%d elapsed=%s ns/op=%.3f\n", s, el, float64(el.Nanoseconds())/total)
}
