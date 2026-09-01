package main

import "testing"

var sink float64

// areaDirect 直接调用：编译期定址（用 noinline 固定为真实调用，公平对照）。
//
//go:noinline
func areaDirect(r Rect) float64 { return r.W * r.H }

// BenchmarkDirectValue：直接调用基准确对照。
func BenchmarkDirectValue(b *testing.B) {
	r := Rect{W: 2, H: 3}
	for i := 0; i < b.N; i++ {
		sink = areaDirect(r)
	}
}

// BenchmarkIfaceDispatch：接口动态分派。shapes[i&1] 让具体类型在 circle/rect 间
// 交替——编译器无法在编译期确定类型，只能走 itab 间接跳转（去虚拟化失效）。
func BenchmarkIfaceDispatch(b *testing.B) {
	shapes := []Shape{Circle{R: 2}, Rect{W: 2, H: 3}}
	for i := 0; i < b.N; i++ {
		sink = shapes[i&1].Area()
	}
}

// BenchmarkBoxing：int 装箱进空接口（any）。小整数进静态表不一定分配，
// 但装箱路径本身（构造 eface、类型转换）有成本。
func BenchmarkBoxing(b *testing.B) {
	var anyv any
	for i := 0; i < b.N; i++ {
		anyv = i
	}
	sink = float64(anyv.(int))
}
