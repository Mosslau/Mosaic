// 来源：ph13-perf-optimization 练习 2 参考实现 —— 分析高并发接口（先 profile 再优化）
// 一句话说明：一个返回设备状态 JSON 的 HTTP handler，朴素版用 fmt.Sprintf（反射 +
// 每次分配），优化版用 sync.Pool 复用 strings.Builder + strconv.AppendInt；
// 附 CPU profile 采集函数，证明「先看热点再动手」的完整流程。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go test -run='^$' -bench=. -benchmem -benchtime=500000x -count=5
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **81.8%**（缺口为 main 演示装配与部分错误分支）
// benchmark 实测（go1.25.6，Apple M4 Pro，-benchtime=500000x -count=5，并发 RunParallel）：
//
//	BenchmarkWriteBodyNaive-14  500000    25.24 ns/op    0 B/op    0 allocs/op
//	BenchmarkWriteBodyFast-14   500000     8.677 ns/op   0 B/op    0 allocs/op
//
// 结论：Fast 版快约 2~3 倍（本机重跑区间约 2~6 倍：naive 波动大 10~62 ns，
// fast 稳定 8~13 ns）。注意两版都是 0 allocs/op——io.Discard 直写基准里
// 参数装箱被编译器留在栈上（未逃逸），分配差异不显现；两版差异来自 fmt 的
// 格式串解析与内部缓冲 vs 常量直写 + strconv.AppendInt（数字随机器波动，以本机重跑为准）
package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"runtime/pprof"
	"strconv"
	"sync"
	"time"
)

// NaiveHandler 朴素版：fmt.Fprintf = 反射解析格式串 + 参数装箱（id 与 ts 各一次）+ fmt 内部缓冲
func NaiveHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	writeBodyNaive(w, r.URL.Query().Get("id"), time.Now().Unix())
}

// writeBodyNaive 响应体写入（朴素版）：Fprintf 的格式串解析与 interface{} 装箱是热路径成本
func writeBodyNaive(w io.Writer, id string, ts int64) {
	fmt.Fprintf(w, `{"device_id":"%s","status":"online","ts":%d}`, id, ts)
}

// bufPool 复用响应缓冲（sync.Pool 三要素：Get → Reset → Put）
var bufPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}

// FastHandler 优化版：池化 bytes.Buffer + 常量直写 + strconv.AppendInt 免装箱，
// 最后 buf.Bytes() 直接写给 ResponseWriter——不经过 string 转换，热路径零分配
func FastHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	writeBodyFast(w, r.URL.Query().Get("id"), time.Now().Unix())
}

// writeBodyFast 响应体写入（优化版）：热点函数抽出来单独可测可 bench——
// 连同 httptest.NewRecorder 一起测会被测试桩的分配淹没（实测：整 handler 基准里
// 两版差异约 7%，457 vs 424 ns/op，14 vs 12 allocs/op；而热点函数本身差约 3 倍），
// profile 定位的热点函数本身才是优化效果的正确度量对象
func writeBodyFast(w io.Writer, id string, ts int64) {
	buf := bufPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer bufPool.Put(buf)

	buf.WriteString(`{"device_id":"`)
	buf.WriteString(id)
	buf.WriteString(`","status":"online","ts":`)
	var num [20]byte // int64 十进制最长 20 位，栈上数组零分配
	buf.Write(strconv.AppendInt(num[:0], ts, 10))
	buf.WriteByte('}')
	_, _ = w.Write(buf.Bytes()) // Bytes() 是引用不是拷贝：零分配直写；Write 错误无关紧要（响应已尽力写出）
}

// ProfileCPU 对 handler 压 load 秒并采集 CPU profile 到 path——
// 用 go tool pprof -top 看热点在 fmt.Sprintf 还是别处（先 profile 再优化）
func ProfileCPU(path string, h http.HandlerFunc, load time.Duration) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	if err := pprof.StartCPUProfile(f); err != nil {
		return err
	}
	defer pprof.StopCPUProfile()

	req, _ := http.NewRequest(http.MethodGet, "/api/devices?id=car-001", nil)
	deadline := time.Now().Add(load)
	for time.Now().Before(deadline) {
		rec := httptest.NewRecorder()
		h(rec, req)
	}
	return nil
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/devices", FastHandler)
	fmt.Println("GET /api/devices?id=car-001 已挂载（main 仅演示装配，压测见 benchmark）")
	_ = mux
}
