// 来源：ph16-pgo-advanced-perf 综合项目（cmd/loadgen，压测/负载生成器入口）
// 一句话说明：internal/workload 的薄 CLI——向 apiserver 发 N 个并发请求并打印
// 延迟分位数与吞吐报告。pgo-experiment.sh 在采集 profile 与跑对比时都调它。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行（cd project）：
//
//	go run ./cmd/loadgen -url http://127.0.0.1:18090 -n 20000 -workers 8 -devices 2048
//
// 验证状态：已验证（go1.25.6，2026-09-02 首验；2026-09-03 修复"Run 失败仍 exit 0"
// 问题——改 os.Exit(1)——后复验 go vet/test/build 全绿）
package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	"tenetlang/go/ph16-pgo-advanced-perf/project/internal/workload"
)

func main() {
	url := flag.String("url", "http://127.0.0.1:18090", "apiserver 基址")
	n := flag.Int("n", 20000, "总请求数")
	workers := flag.Int("workers", 8, "并发连接数")
	devices := flag.Int("devices", 2048, "设备范围")
	timeout := flag.Duration("timeout", 10*time.Second, "单请求超时")
	flag.Parse()

	s, err := workload.Run(workload.Config{
		URL:     *url,
		Total:   *n,
		Workers: *workers,
		Devices: *devices,
		Timeout: *timeout,
	})
	if err != nil {
		// 失败必须非零退出：pgo-experiment.sh 会把 loadgen 输出重定向到报告文件，
		// 只打印并 return 会 exit 0——服务没起来时静默产出空报告、脚本还当成功。
		fmt.Fprintln(os.Stderr, "loadgen:", err)
		os.Exit(1)
	}
	fmt.Printf("requests=%d ok=%d wall=%s throughput=%.0f req/s\n",
		s.Total, s.OK, s.Wall.Round(time.Millisecond), s.Throughput)
	fmt.Printf("latency(µs): p50=%.2f p95=%.2f p99=%.2f mean=%.2f\n",
		s.P50, s.P95, s.P99, s.Mean)
}
