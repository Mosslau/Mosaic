// 来源：ph16-pgo-advanced-perf 练习 1 参考实现（sol-01-collect-profile，采集压测 profile）
// 一句话说明：一个自带压测循环的 CLI——--load 并发压测自己的 CPU 密集函数，
// 同时用 runtime/pprof 采集窗口期内的 CPU profile，跑完用 go tool pprof 回答
// "热点是不是压在预期函数上"。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd sol-01-collect-profile；产物一律 /tmp）：
//
//	# 1. 测试 + 构建
//	go test ./... && go vet ./... && go build -o /tmp/ph16/sol01 .
//	# 2. 4 路并发压测 2 秒并采集 profile
//	/tmp/ph16/sol01 -workers 4 -dur 2s -cpuprofile /tmp/ph16/sol01.pprof
//	# 3. 验证热点在 compressBlock
//	go tool pprof -top -nodecount=5 /tmp/ph16/sol01 /tmp/ph16/sol01.pprof
//
// 验证块（go1.25.6 实测，2026-09-03，采样计数随机器波动）：
//
//	$ /tmp/ph16/sol01 -workers 4 -dur 2s -cpuprofile /tmp/ph16/sol01.pprof
//	processed=1287013 blocks, elapsed=2s, sink=ba77d09351b81c45
//	$ go tool pprof -top -nodecount=5 ...
//		4.99s  84.01%  main.compressBlock (inline)  ← 热点如预期压在业务函数
//		                                        （4 worker × 2s ≈ 5.4s cum，另有 asyncPreempt 长尾）
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
	"sync/atomic"
	"time"
)

// compressBlock 模拟"压缩一个数据块"的 CPU 密集函数：对 4KB 块逐字节混合。
// 零分配，profile 里它是唯一该出现的业务帧。
func compressBlock(block []byte) uint64 {
	var h uint64 = 1469598103934665603
	for i := 0; i < len(block); i++ {
		h ^= uint64(block[i]) + uint64(i)
		h *= 1099511628211
		h ^= h >> 13
	}
	return h
}

// main 的组织方式："压测"与"采集"是两个正交开关——
// -workers 控制并发负载，-dur 控制窗口，-cpuprofile 控制采集。
// 三者叠加就是"采集压测 profile"的最小闭环（对应 roadmap §16 练习 1）。
func main() {
	workers := flag.Int("workers", 4, "并发压测 goroutine 数")
	dur := flag.Duration("dur", 2*time.Second, "压测时长")
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

	var blocks uint64
	results := make([]uint64, *workers)
	deadline := time.Now().Add(*dur)
	done := make(chan struct{})
	start := time.Now()
	for w := 0; w < *workers; w++ {
		go func(seed uint64, out *uint64) {
			block := make([]byte, 4096)
			for i := range block {
				block[i] = byte(seed + uint64(i))
			}
			var h uint64
			for time.Now().Before(deadline) {
				h ^= compressBlock(block)
				atomic.AddUint64(&blocks, 1)
			}
			*out = h // 每 worker 的混合结果落地，防止循环被优化掉
			done <- struct{}{}
		}(uint64(w)*7919, &results[w])
	}
	for w := 0; w < *workers; w++ {
		<-done
	}
	var sink uint64
	for _, h := range results {
		sink ^= h
	}
	fmt.Printf("processed=%d blocks, elapsed=%s, sink=%x\n",
		blocks, time.Since(start).Round(time.Millisecond), sink)
}
