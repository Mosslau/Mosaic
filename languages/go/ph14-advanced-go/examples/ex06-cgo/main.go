// 来源：ph14-advanced-go 示例 6 —— cgo：调用 C 库
// 一句话说明：cgo 让 Go 程序直接调用 C 代码——本示例做两件事：
// ① 调用自定义 C 库（c_lib/addvec.c：向量加法）——完整演示"写 C 库 → cc 编译成
// 静态库 → cgo 链接 → Go 调用"的闭环；② 调用系统 C 数学库 libm 的 sin（-lm 链接）。
// 注意三个 cgo 知识点：preamble（import "C" 前的注释块）里写头文件与链接指令；
// C 类型映射（C.int / C.size_t）；切片指针 → C 指针的 unsafe.Pointer 桥接。
// 验证环境：go1.25.6（darwin/arm64），CGO_ENABLED=1，cc = Apple clang 21.0.0
// 依赖：零第三方（C 库源码在本模块 c_lib/ 下，需先编译成静态库）
// 运行（先编译 C 库，再跑 Go）：
//
//	# 1. 编译 C 库到 /tmp（产物不落仓库）
//	cc -c -o /tmp/addvec.o c_lib/addvec.c
//	ar rcs /tmp/libaddvec.a /tmp/addvec.o
//	# 2. 构建 + 测试 + 运行（CFLAGS/LDFLAGS 指向 /tmp 下的库）
//	CGO_ENABLED=1 go test -v ./...
//	CGO_ENABLED=1 go vet ./...
//	CGO_ENABLED=1 go run .
//
// 验证状态：已验证（go1.25.6 + clang 21.0.0，实测输出见 README）
package main

/*
#cgo CFLAGS: -I/Users/ninebot/code/mosslau/TenetLang/languages/go/ph14-advanced-go/examples/ex06-cgo/c_lib
#cgo LDFLAGS: /tmp/libaddvec.a -lm
#include <addvec.h>
extern double sin(double); // libm 的 sin；-lm 提供链接（macOS 上 libSystem 已含，仍显式声明）
*/
import "C"

import (
	"fmt"
	"math"
	"unsafe"
)

// addVec 封装：[]int32 → C 数组 → addvec → 写回 []int32。
// 教学点：C 只认指针，Go 切片要 unsafe.Pointer(&s[0]) 桥接；元素类型必须匹配
// C.int（32 位）；len 显式传给 C.size_t，C 侧不做边界检查——越界是 C 的世界。
func addVec(a, b []int32) []int32 {
	if len(a) != len(b) {
		panic("addVec: length mismatch")
	}
	out := make([]int32, len(a))
	if len(a) == 0 {
		return out
	}
	C.addvec(
		(*C.int)(unsafe.Pointer(&a[0])),
		(*C.int)(unsafe.Pointer(&b[0])),
		(*C.int)(unsafe.Pointer(&out[0])),
		C.size_t(len(a)),
	)
	return out
}

// addScalar 封装最简单的 C 标量函数。
func addScalar(x, y int32) int32 {
	return int32(C.add(C.int(x), C.int(y)))
}

// sinViaC 用 libm 的 sin。
func sinViaC(x float64) float64 {
	return float64(C.sin(C.double(x)))
}

func main() {
	a := []int32{1, 2, 3, 4}
	b := []int32{10, 20, 30, 40}
	fmt.Println("addvec:", addVec(a, b)) // [11 22 33 44]
	fmt.Println("add(7, 8):", addScalar(7, 8))
	fmt.Printf("sin(pi/2) via libm: %.1f（对照 Go math.Sin: %.1f）\n",
		sinViaC(math.Pi/2), math.Sin(math.Pi/2))
}
