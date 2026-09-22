// 来源：ph16-pgo-advanced-perf 示例 ex04-alloc-opt（内存布局与分配优化前后对比）
// 一句话说明：同一功能的"朴素版 vs 优化版"对照——
// (1) 遥测格式化：fmt.Sprintf+字符串+=  vs  strings.Builder 预分配+strconv 免装箱；
// (2) 结构体布局：字段乱序（padding 膨胀） vs 按对齐降序排列（同数据更小占用）。
// 两组都在 benchmark 里实测三列指标（ns/op、B/op、allocs/op）。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd ex04-alloc-opt）：
//
//	# 1. 正确性：两版输出必须逐字节一致
//	go test -v ./...
//	# 2. 分配优化对比（格式化）
//	go test -run='^$' -bench='Format' -benchmem -count=5
//	# 3. 内存布局对比（结构体切片）
//	go test -run='^$' -bench='Layout' -benchmem -count=5
//	# 4. demo 输出（两版格式化结果一致 + 结构体尺寸对比）
//	go run .
//
// 验证块（go1.25.6 实测，2026-09-03，-count=5 取中位数，数字随机器波动 ±10~20%）：
//
//	BenchmarkFormatNaive-14      694   1704325 ns/op  22907866 B/op  3547 allocs/op
//	BenchmarkFormatOpt-14      59409     20338 ns/op     98304 B/op     2 allocs/op
//	    ← 快约 84×、内存省 233×、分配次数 3547→2（每事件 3.5 次分配 → 整体 2 次）
//	BenchmarkLayoutBad-14       1394    822069 ns/op   4005898 B/op     1 allocs/op
//	BenchmarkLayoutGood-14      3805    327155 ns/op   3203077 B/op     1 allocs/op
//	    ← 同数据省 20% 内存（4.0MB→3.2MB），遍历快约 2.5×（缓存行装得更多）
//	go run . 输出：naive==opt: true；sizeof(BadEvent)=40 sizeof(GoodEvent)=32（go1.25 arm64）
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"fmt"
	"strconv"
	"strings"
	"unsafe"
)

// Event 是一条设备遥测事件。
type Event struct {
	DeviceID  string
	LatencyMs int
	Online    bool
}

// FormatNaive 朴素版：每事件一次 fmt.Sprintf（内部多次装箱+分配），结果用 += 拼接
// （每次 += 都整体拷贝已有内容，O(n²)）。
func FormatNaive(events []Event) string {
	s := ""
	for _, e := range events {
		s += fmt.Sprintf("device=%s latency=%dms online=%t\n", e.DeviceID, e.LatencyMs, e.Online)
	}
	return s
}

// FormatOpt 优化版：Builder.Grow 一次性预分配（容量按每条约 40 字节估算），
// 数字用 strconv.AppendInt 写进栈上 scratch 再拷贝——避开 strconv.Itoa 的堆分配，
// bool 用查表字符串避免 fmt 的装箱。全程只剩 Builder 底层数组扩容的极少数分配。
func FormatOpt(events []Event) string {
	var sb strings.Builder
	sb.Grow(len(events) * 40) // 预估每条约 40 字节
	var scratch [20]byte      // int64 十进制最长 20 位，栈上复用
	for _, e := range events {
		sb.WriteString("device=")
		sb.WriteString(e.DeviceID)
		sb.WriteString(" latency=")
		sb.Write(strconv.AppendInt(scratch[:0], int64(e.LatencyMs), 10))
		sb.WriteString("ms online=")
		sb.WriteString(strconv.FormatBool(e.Online))
		sb.WriteByte('\n')
	}
	return sb.String()
}

// BadEvent 字段乱序：bool(1B) 与 int(8B)、string(16B) 交错，编译器被迫插入 padding。
type BadEvent struct {
	Online    bool   // 1B + 7B padding
	LatencyMs int    // 8B
	Valid     bool   // 1B + 7B padding
	DeviceID  string // 16B
}

// GoodEvent 同样的四个字段按对齐需求降序排列：大对齐字段在前，小字段收尾。
// 数据一模一样，尺寸却小一档——结构体数组/切片里这就是真实的内存节省。
type GoodEvent struct {
	DeviceID  string // 16B
	LatencyMs int    // 8B
	Online    bool   // 1B
	Valid     bool   // 1B（+6B 尾部 padding 到 8 对齐）
}

func main() {
	events := []Event{
		{DeviceID: "dev-001", LatencyMs: 12, Online: true},
		{DeviceID: "dev-002", LatencyMs: 250, Online: false},
	}
	fmt.Println("naive==opt:", FormatNaive(events) == FormatOpt(events))
	fmt.Println("sizeof(BadEvent) =", unsafe.Sizeof(BadEvent{}))  // 40：两份 7B padding
	fmt.Println("sizeof(GoodEvent)=", unsafe.Sizeof(GoodEvent{})) // 32：同数据省 20%
}
