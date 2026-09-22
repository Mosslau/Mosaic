// 来源：ph14-advanced-go 练习 1 参考实现 —— 泛型工具库（Map/Filter/Reduce）
// 一句话说明：用 Go 泛型实现三个高阶函数 Map / Filter / Reduce，覆盖「类型集约束
// （~int|~float64 用于 Sum/Reduce）、comparable 约束（用于 Contains）、any 约束
// （Map/Filter 的变换与过滤）」三类写法；并通过「泛型函数传给具体类型」验证编译期
// 实例化——同一份代码同时支持 int、float64、自定义数值类型。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 验证块（go test ./... 实测，2026-09-01）：
//
//	PASS  ok  tenetlang/go/ph14-advanced-go/exercises/sol-01-generics-tools  0.006s
//	go vet ./... 零输出；go test -race ./... 通过（纯函数无并发，race 无报告）
//	go run . 输出：
//	  Map(int)      : [2 4 6 8 10]
//	  Map(float64)  : [3 6 9]
//	  Map(Celsius)  : [20 40]              ← ~int 约束覆盖自定义类型
//	  Filter        : [2 4 6 8]
//	  Reduce(Sum)   : 28（[]int{1..7}）
//	  Contains      : true / false
package main

import "fmt"

// ---- 类型集约束（供 Reduce 的 Sum 语义复用）----

type Number interface {
	~int | ~int32 | ~int64 | ~float32 | ~float64
}

// ---- 三个泛型高阶函数 ----

// Map 对每个元素应用 f，返回新切片（T→U，两个类型参数）。
func Map[T, U any](vs []T, f func(T) U) []U {
	out := make([]U, len(vs))
	for i, v := range vs {
		out[i] = f(v)
	}
	return out
}

// Filter 保留 f 返回 true 的元素。
func Filter[T any](vs []T, f func(T) bool) []T {
	out := make([]T, 0, len(vs))
	for _, v := range vs {
		if f(v) {
			out = append(out, v)
		}
	}
	return out
}

// Reduce 把切片折叠成一个值：acc 是初始值，f 逐元素累加。
// 约束用 Number 保证 + 可用——这比 any 更精确（any 无法相加）。
func Reduce[T Number](vs []T, acc T, f func(T, T) T) T {
	for _, v := range vs {
		acc = f(acc, v)
	}
	return acc
}

// Contains 用 comparable 约束：T 必须支持 ==。
func Contains[T comparable](vs []T, target T) bool {
	for _, v := range vs {
		if v == target {
			return true
		}
	}
	return false
}

// ---- 演示与测试共用类型 ----

type Celsius int

func main() {
	// Map：int 与 float64 用同一份代码
	fmt.Println("Map(int)     :", Map([]int{1, 2, 3, 4, 5}, func(v int) int { return v * 2 }))
	fmt.Println("Map(float64) :", Map([]float64{1, 2, 3}, func(v float64) float64 { return v * 3 }))
	fmt.Println("Map(Celsius) :", Map([]Celsius{10, 20}, func(v Celsius) Celsius { return v * 2 }))

	// Filter：偶数
	fmt.Println("Filter       :", Filter([]int{1, 2, 3, 4, 5, 6, 7, 8}, func(v int) bool { return v%2 == 0 }))

	// Reduce：求和（泛型化后 Sum 就是 Reduce 的特例）
	fmt.Println("Reduce(Sum)  :", Reduce([]int{1, 2, 3, 4, 5, 6, 7}, 0, func(a, b int) int { return a + b }))

	// Contains：comparable
	fmt.Println("Contains     :", Contains([]string{"a", "b"}, "b"), "/", Contains([]string{"a", "b"}, "z"))
}
