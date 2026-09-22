// 来源：ph13-perf-optimization 示例 2 —— 逃逸分析（escape analysis）
// 一句话说明：编译器决定变量住在栈（函数返回即回收，零成本）还是堆（GC 管理，有成本）；
// go build -gcflags='-m' 把裁决过程打印出来。本文件四个函数对应四种典型裁决，
// 下方输出为 go1.25.6 实机运行结果（行号与本文件一致）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go build -gcflags='-m' .        # 打印逃逸裁决（输出到 stderr，实际节选）：
//
//	./main.go:36:2: moved to heap: p        ← makePoint：返回局部变量地址，p 搬到堆
//	./main.go:52:6: moved to heap: b        ← bigBuf：1 MiB 对象太大，栈放不下
//	./main.go:59:17: len(s) escapes to heap ← printLen：len(s) 装箱进 interface{} 参数
//
// 验证状态：已验证（go1.25.6）；行号随代码改动漂移，结论（谁逃逸、为什么）稳定
package main

import "fmt"

// Point 演示用结构体
type Point struct{ X, Y int }

// SumTo 不逃逸：n 与 s 只活在栈上，函数返回即回收，零堆分配
func SumTo(n int) int {
	s := 0
	for i := 0; i <= n; i++ {
		s += i
	}
	return s
}

// makePoint 逃逸：返回局部变量地址，p 必须活到调用者手里 → moved to heap（1 次分配）
//
//go:noinline
func makePoint() *Point {
	p := Point{X: 1, Y: 2}
	return &p
}

// makePointVal 不逃逸：按值返回，p 留在栈上，零分配（与 makePoint 逐行对照）
//
//go:noinline
func makePointVal() Point {
	p := Point{X: 1, Y: 2}
	return p
}

// bigBuf 逃逸：对象太大（1 MiB），栈放不下 → moved to heap（即使不返回）
//
//go:noinline
func bigBuf() int {
	var b [1 << 20]byte
	b[0] = 1
	return int(b[0])
}

// printLen 逃逸：len(s) 的返回值装箱成 interface{} 传给 fmt.Println → escapes to heap
func printLen(s string) {
	fmt.Println(len(s))
}

func main() {
	fmt.Println(SumTo(100), makePoint(), makePointVal(), bigBuf())
	printLen("escape analysis")
}
