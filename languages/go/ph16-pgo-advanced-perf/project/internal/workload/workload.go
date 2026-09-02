// 包 workload：HTTP 压测/负载生成器（库形式，命令行入口见 cmd/loadgen）。
// 对 apiserver 持续发 GET /api/devices/{id}，逐请求记录延迟样本，
// 输出 p50/p95/p99/均值与吞吐（req/s）。两种职责：
//  1. 产生"代表性负载"——把服务压到 CPU 忙，期间由 scripts/pgo-experiment.sh
//     curl /debug/pprof/profile?seconds=N 采集服务端 CPU profile（PGO 的输入）；
//  2. 报告基线与 -pgo 两个二进制的端到端延迟/吞吐，供对比（roadmap §16 推荐项目
//     「API 服务 PGO 实验」的验收动作）。
package workload

import (
	"fmt"
	"io"
	"net/http"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

// Config 是压测参数。
type Config struct {
	URL     string        // 服务基址，如 http://127.0.0.1:18090
	Total   int           // 总请求数
	Workers int           // 并发连接数
	Devices int           // 设备范围（id 取 [0, Devices)）
	Timeout time.Duration // 单请求超时
}

// Summary 是一次压测的报告。
type Summary struct {
	Total      int
	Wall       time.Duration
	Throughput float64 // req/s
	P50        float64 // µs
	P95        float64 // µs
	P99        float64 // µs
	Mean       float64 // µs
	OK         int     // HTTP 200 计数（服务端正确性抽样）
}

// Run 发起压测并返回报告。请求 ID 用原子计数器分发：
// 并发 worker 各自领取连续编号，设备 id = (n-1) % Devices，保证覆盖均匀且可复现。
func Run(cfg Config) (*Summary, error) {
	if cfg.Total <= 0 || cfg.Workers <= 0 {
		return nil, fmt.Errorf("workload: Total/Workers 必须为正（got %d/%d）", cfg.Total, cfg.Workers)
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 10 * time.Second
	}
	if cfg.Devices <= 0 {
		cfg.Devices = cfg.Total
	}

	// 显式 Transport：默认 MaxIdleConnsPerHost=2，8 个并发 worker 会频繁建新连接
	// （本机实测：5 万请求产生 6k+ TIME_WAIT、临时端口耗尽导致 curl 采 profile 失败
	// EADDRNOTAVAIL——压测的是 TCP 握手而非业务）。按 worker 数放宽空闲连接池，
	// 让压测真正打 CPU 热点而不是握手。
	transport := &http.Transport{
		MaxIdleConns:        cfg.Workers * 2,
		MaxIdleConnsPerHost: cfg.Workers * 2,
		IdleConnTimeout:     90 * time.Second,
	}
	client := &http.Client{Timeout: cfg.Timeout, Transport: transport}

	var (
		mu      sync.Mutex
		lats    = make([]float64, 0, cfg.Total) // µs；预分配避免 append 扩容
		okCount atomic.Int64
		counter atomic.Int64
		wg      sync.WaitGroup
	)

	collect := func(l float64) {
		mu.Lock()
		lats = append(lats, l)
		mu.Unlock()
	}

	for w := 0; w < cfg.Workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				n := int(counter.Add(1))
				if n > cfg.Total {
					return
				}
				url := fmt.Sprintf("%s/api/devices/%d", cfg.URL, (n-1)%cfg.Devices)
				t0 := time.Now()
				resp, err := client.Get(url)
				dt := time.Since(t0)
				if err == nil {
					io.Copy(io.Discard, resp.Body)
					resp.Body.Close()
					if resp.StatusCode == http.StatusOK {
						okCount.Add(1)
					}
				}
				collect(float64(dt.Nanoseconds()) / 1000.0)
			}
		}()
	}

	start := time.Now()
	wg.Wait()
	wall := time.Since(start)

	mu.Lock()
	sorted := make([]float64, len(lats))
	copy(sorted, lats)
	mu.Unlock()

	sort.Float64s(sorted)
	per := func(q float64) float64 {
		if len(sorted) == 0 {
			return 0
		}
		return sorted[int(q*float64(len(sorted)))-1]
	}
	var sum float64
	for _, l := range sorted {
		sum += l
	}
	if len(sorted) == 0 {
		return nil, fmt.Errorf("workload: 没有完成任何请求")
	}
	return &Summary{
		Total:      len(sorted),
		Wall:       wall,
		Throughput: float64(len(sorted)) / wall.Seconds(),
		P50:        per(0.50),
		P95:        per(0.95),
		P99:        per(0.99),
		Mean:       sum / float64(len(sorted)),
		OK:         int(okCount.Load()),
	}, nil
}
