// 来源：ph14-advanced-go 示例 4 —— interface 动态分派：iface 布局、类型断言与 nil 陷阱
// 一句话说明：接口变量的运行时形态是一个双字（two-word）头——方法表指针（itab，含
// 具体类型与函数指针表）+ 数据指针（或直接内联的小值）。调用接口方法 = 通过 itab 查
// 函数指针间接跳转（动态分派），而直接调用 = 编译期定址直接跳转。本示例演示：
// ① 同一接口变量换装不同类型后方法的动态分派；② 类型断言（comma-ok 与 panic 两种）、
// ③ 类型 switch、④ 空接口装箱与 %T 的反射语义、⑤ 三个 nil 陷阱（nil 接口本身、
// 持有 nil 指针的接口、nil 接口上的方法调用 panic）；
// ⑥ 分派成本实测（benchmark：直接调用 vs 接口分派 vs 装箱，见 bench_test.go）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//	go test -run='^$' -bench=. -benchmem -benchtime=5000000x   # 分派成本实测
//
// 验证状态：已验证（go1.25.6）；benchmark 数字随机器波动，趋势稳定（见 README）
package main

import "fmt"

// Shape 两个方法的接口——方法表里有两项函数指针。
type Shape interface {
	Area() float64
	Name() string
}

// Circle / Rect 都隐式实现 Shape（Go 的接口实现是结构性的，无需显式声明）。
type Circle struct{ R float64 }

func (c Circle) Area() float64 { return 3.14159 * c.R * c.R }
func (c Circle) Name() string  { return "circle" }

type Rect struct{ W, H float64 }

func (r Rect) Area() float64 { return r.W * r.H }
func (r Rect) Name() string  { return "rect" }

// 值接收者 vs 指针接收者：只有 *Circle 同时拥有值/指针方法集；Circle 只有值方法集。
type Square struct{ Side float64 }

func (s Square) Area() float64 { return s.Side * s.Side }
func (s Square) Name() string  { return "square" }

// describe 空接口（any = interface{}）装箱 + %T：运行时类型信息来自 itab 里的类型指针。
func describe(v any) {
	fmt.Printf("  %T (value=%v)\n", v, v)
}

// 三个 nil 陷阱演示
func nilTraps() {
	var s Shape
	fmt.Printf("  ① 零值接口 s == nil? %v（真 nil：itab 与 data 都是零值）\n", s == nil)
	// s.Area() // panic: runtime error: invalid memory address——nil 接口没有方法可调

	var p *Rect
	s = p
	fmt.Printf("  ② 接口装着 nil *Rect：s == nil? %v（假！itab 有类型、data 是 nil 指针）\n", s == nil)
	if s == nil { // 常见的错误判空
		fmt.Println("    （这里不会进——正是坑）")
	}
	r, ok := s.(*Rect) // 断言成功，但拿到的是 nil 指针
	fmt.Printf("  ③ 断言 *Rect: ok=%v, 但指针是 nil? %v（断言不检查值，只检查类型）\n", ok, r == nil)
}

func main() {
	fmt.Println("== 1. 动态分派：同一 Shape 变量换装不同类型 ==")
	var s Shape
	s = Circle{R: 2}
	fmt.Printf("  %s: area=%.2f\n", s.Name(), s.Area())
	s = Rect{W: 3, H: 4}
	fmt.Printf("  %s: area=%.2f\n", s.Name(), s.Area())
	s = Square{Side: 5}
	fmt.Printf("  %s: area=%.2f\n", s.Name(), s.Area())

	fmt.Println("== 2. 类型断言：comma-ok 与单返回值（panic）两种 ==")
	s = Rect{W: 3, H: 4}
	r, ok := s.(Rect)
	fmt.Printf("  s.(Rect): ok=%v area=%.1f\n", ok, r.Area())
	_, ok = s.(Circle)
	fmt.Printf("  s.(Circle): ok=%v（失败时值域是零值，不 panic）\n", ok)
	// c2 := s.(Circle) // 单返回值断言：类型不符直接 panic

	fmt.Println("== 3. 类型 switch ==")
	classify := func(v any) string {
		switch t := v.(type) {
		case int:
			return fmt.Sprintf("int %d", t)
		case string:
			return fmt.Sprintf("string %q", t)
		case Rect:
			return fmt.Sprintf("Rect %v", t)
		case nil:
			return "nil"
		default:
			return fmt.Sprintf("other %T", v)
		}
	}
	for _, v := range []any{42, "hi", Rect{W: 1, H: 2}, nil, 3.14} {
		fmt.Printf("  %v → %s\n", v, classify(v))
	}

	fmt.Println("== 4. 空接口装箱 ==")
	describe(42)
	describe("text")

	fmt.Println("== 5. nil 陷阱 ==")
	nilTraps()
}
