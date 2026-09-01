// 来源：ph13-perf-optimization 示例 4 —— sync.Pool 复用临时对象
// 一句话说明：高频短生命周期的临时对象（这里是 4 KiB 缓冲）用 sync.Pool 复用，
// 把 allocs/op 从每轮 1 次降到 0 次；并验证 Pool 在 GC 时会被清空（只存临时对象的前提），
// 以及「小响应体朴素版反而更快」的边界（实测见 README，Pool 不是无条件更快）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go test -run='^$' -bench=. -benchmem -benchtime=100000x   # 并发基准，看 allocs/op 差异
//
// 验证状态：已验证（go1.25.6）；benchmark 数字随机器波动，以 README 实测记录为准
package main

import (
	"bytes"
	"fmt"
	"sync"
)

// bufPool 复用 *bytes.Buffer：New 只在池空时调用；对象在 GC 后可能被清空，随时能新建
var bufPool = sync.Pool{
	New: func() any { return new(bytes.Buffer) },
}

// checksum 伪造一个「处理结果」，防止编译器把缓冲写操作优化掉
func checksum(buf *bytes.Buffer) int {
	b := buf.Bytes()
	sum := 0
	for i := 0; i < len(b); i += 512 {
		sum += int(b[i])
	}
	return sum
}

// ProcessNoPool 每次调用新建缓冲：实测每次 1 次堆分配（4 KiB 负载下内部 []byte 扩容一次，
// 4096 B/op）；Buffer 结构本身因 checksum 内联留在栈上（0 次）——「大负载 > 64 B 时扩容必发生」
func ProcessNoPool(data []byte) int {
	var buf bytes.Buffer
	buf.Write(data)
	return checksum(&buf)
}

// ProcessPool 从池里借缓冲：热路径零分配（池命中时 New 不执行）
// 三要素：Get → 用前 Reset（池里的对象是脏的）→ 用后 Put
func ProcessPool(data []byte) int {
	buf := bufPool.Get().(*bytes.Buffer)
	buf.Reset() // 关键：池中的对象带着上一次使用的内容，不复位就会串数据
	defer bufPool.Put(buf)
	buf.Write(data)
	return checksum(buf)
}

func main() {
	data := bytes.Repeat([]byte("abcdefghij"), 409) // 4090 字节
	fmt.Println(ProcessNoPool(data), ProcessPool(data))
}
