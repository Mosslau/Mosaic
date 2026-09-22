// 来源：ph16-pgo-advanced-perf 综合项目（cmd/apiserver，带 pprof 端点的 API 服务）
// 一句话说明：设备签名 API 服务——GET /api/devices/{id} 返回设备信息 + 对设备遥测样本
// 做逐字节签名（Signer 接口分派：90% fnvSigner / 10% xorSigner，算法可插拔的形态）。
// 每个请求的签名循环是纯 CPU 热点且走接口调用——这正是 PGO 去虚拟化能作用的地方。
// /debug/pprof/* 挂在服务进程内（net/http/pprof 的标准手动注册形态），
// 压测期间 curl /debug/pprof/profile?seconds=N 即可采到"负载真在跑"的 CPU profile。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd project；产物一律 /tmp）：
//
//	go test ./... && go vet ./...            # 测试（含核心签名 benchmark）
//	go run ./cmd/apiserver -addr 127.0.0.1:18090 -devices 2048 -samples 8192 &
//	curl -s http://127.0.0.1:18090/api/devices/1    # 单请求冒烟
//	# pprof 端点（压测时采 5 秒，见 scripts/pgo-experiment.sh 的完整编排）
//	curl -s 'http://127.0.0.1:18090/debug/pprof/profile?seconds=5' > /tmp/ph16proj/server.pprof
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"net/http"
	"net/http/pprof"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// Signer 是签名算法接口：服务把"签什么"固定、"怎么签"做成可插拔
// （换算法不停机、A/B 对比），代价是每次调用走 itab 间接跳转。
// PGO 看到签名热点里 90% 是 fnvSigner 后，会在调用点插入类型断言，
// 把间接调用改写为直接调用并内联（本阶段的核心机制，见 examples/ex02）。
type Signer interface {
	Step(uint64) uint64
}

// fnvSigner 占 90% 设备：FNV 风格的乘加混合。带配置字段（A/C）——
// 间接调用会阻止编译器把字段加载提升出签名循环，去虚拟化 + 内联后才解锁该提升。
type fnvSigner struct {
	A uint64
	C uint64
}

func (s *fnvSigner) Step(x uint64) uint64 { return x*s.A + s.C }

// xorSigner 占 10% 设备：异或折叠。它的存在让调用点保持接口形态。
type xorSigner struct{}

func (*xorSigner) Step(x uint64) uint64 {
	x ^= x >> 33
	x *= 0xff51afd7ed558ccd
	return x ^ (x >> 29)
}

// Device 是内存中的设备模型：遥测样本预生成（伪随机、确定性），
// 签名时逐样本走 Signer.Step。samples 越多单请求 CPU 越重（见 -samples 说明）。
type Device struct {
	ID      int
	Name    string
	Signer  Signer
	Samples []uint64
}

// newDevices 确定性生成 n 台设备：90% fnvSigner / 10% xorSigner，
// 每台 samples 个遥测样本（LCG 填充）。gen 提前算好，profile 窗口只装"签名"。
func newDevices(n, samples int) []*Device {
	fnv := &fnvSigner{A: 6364136223846793005, C: 1442695040888963407}
	xor := &xorSigner{}
	devs := make([]*Device, n)
	for i := 0; i < n; i++ {
		s := make([]uint64, samples)
		seed := uint64(i+1) * 2654435761
		for j := range s {
			seed = seed*6364136223846793005 + 1442695040888963407
			s[j] = seed
		}
		signer := Signer(fnv)
		if i%10 == 9 {
			signer = xor
		}
		devs[i] = &Device{ID: i, Name: fmt.Sprintf("device-%05d", i), Signer: signer, Samples: s}
	}
	return devs
}

// signDevice 是每请求的热点：对设备遥测逐样本调用 s.Step（样本相互独立，
// 结果异或折叠——乘加延迟可被流水线隐藏，每样本的"调用开销"暴露在关键路径上）。
// //go:noinline 的实测理由同 exercises/sol-02 的 serve 与 sol-04 的 digest：
// 该函数若被内联进 handler，PGO 去虚拟化收益会消失（本机实测），保持独立函数最稳。
//
//go:noinline
func signDevice(d *Device) uint64 {
	var h uint64
	for _, v := range d.Samples {
		h ^= d.Signer.Step(v) // 热点调用点：PGO 在这里去虚拟化到 (*fnvSigner).Step
	}
	return h
}

// handleDevice 返回 GET /api/devices/{id}：查询 + 签名 + JSON 序列化。
// 抽成普通函数便于 main_test 用 httptest 直接断言（不走子进程）。
func handleDevice(devs []*Device) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// 路径形如 /api/devices/123
		raw := strings.TrimPrefix(r.URL.Path, "/api/devices/")
		if raw == "" {
			http.NotFound(w, r)
			return
		}
		id, err := strconv.Atoi(raw)
		if err != nil || id < 0 || id >= len(devs) {
			http.Error(w, `{"error":"device not found"}`, http.StatusNotFound)
			return
		}
		d := devs[id]
		sig := signDevice(d)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"id":%d,"name":%q,"samples":%d,"digest":"%x"}`+"\n",
			d.ID, d.Name, len(d.Samples), sig)
	}
}

// handleHealthz 供负载生成器/探活使用。
func handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintln(w, `{"status":"ok"}`)
}

func newMux(devs []*Device) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", handleHealthz)
	mux.HandleFunc("/api/devices/", handleDevice(devs))
	// 手动挂 pprof 端点（等价于 import _ "net/http/pprof" 注册到 DefaultServeMux；
	// 这里用显式 mux，不与业务路由互相污染）。
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
	return mux
}

func main() {
	addr := flag.String("addr", "127.0.0.1:18090", "HTTP 监听地址")
	devices := flag.Int("devices", 2048, "预生成设备数")
	samples := flag.Int("samples", 8192, "每设备遥测样本数（8B/样本；8192 ≈ 64KB → 单请求纯 CPU ~50µs）")
	flag.Parse()

	devs := newDevices(*devices, *samples)
	log.Printf("apiserver: %d devices × %d samples（%d KiB/设备），%s（%s）",
		*devices, *samples, (*samples*8)/1024, runtime.Version(), runtime.GOARCH)
	log.Printf("listening on %s（pprof: /debug/pprof/profile?seconds=N）", *addr)

	srv := &http.Server{Addr: *addr, Handler: newMux(devs)}

	// 优雅关闭：SIGINT/SIGTERM → Shutdown（参考 ph09 的优雅关闭示例）
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-quit
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("shutdown: %v", err)
		}
	}()

	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("服务退出: %v", err)
	}
}
