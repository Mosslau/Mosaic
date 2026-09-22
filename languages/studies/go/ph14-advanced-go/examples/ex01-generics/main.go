// 来源：ph14-advanced-go 示例 1 —— Generics：类型集约束与类型推断
// 一句话说明：Go 1.18 引入的泛型 = 类型参数 + 约束（constraint）。本示例演示
// 三类约束的写法——① 内置 comparable（可比较，用于 map key / ==）、
// ② 类型集（~int | ~float64 的并集，~ 表示"底层类型"从而覆盖自定义类型）、
// ③ 方法集约束（任何有 String() string 方法的类型）；以及类型推断、显式实例化
// 与类型参数的"实例化在编译期完成、无运行时开销"这一事实。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"strconv"
)

// Number 类型集约束：~ 表示底层类型。~int 同时接受 int 与任何底层类型为 int
// 的自定义类型（如下面的 Celsius）；| 是并集。
type Number interface {
	~int | ~int32 | ~int64 | ~float32 | ~float64
}

// Sum 对任意 Number 切片求和。T 的零值（var s T）与 += 都由类型集保证可行。
func Sum[T Number](vs []T) T {
	var s T
	for _, v := range vs {
		s += v
	}
	return s
}

// Contains 用内置约束 comparable：T 必须支持 ==，才能做相等比较。
// comparable 覆盖所有可比较类型（基本类型、指针、channel、可比较 struct/数组）。
func Contains[T comparable](vs []T, target T) bool {
	for _, v := range vs {
		if v == target {
			return true
		}
	}
	return false
}

// Celsius 自定义数值类型：底层类型是 int，满足 ~int 约束。
type Celsius int

// Stringer 方法集约束：约束不只限于类型集，还可以要求方法存在。
type Stringer interface {
	String() string
}

// Format 接受任何实现 String() string 的类型——多态由"有什么方法"决定，与接口一致。
func Format[T Stringer](v T) string { return v.String() }

// Device 实现 Stringer。
type Device struct{ ID int }

func (d Device) String() string { return fmt.Sprintf("device-%d", d.ID) }

// 类型参数也可以用在泛型类型上：Box 是一个装着 T 的盒子。
type Box[T any] struct {
	Value T
}

func (b Box[T]) Get() T { return b.Value }

// 泛型约束里还可以引用另一个类型参数：Pair 的两个字段类型不同但"同为可比较"。
type Pair[A comparable, B any] struct {
	K A
	V B
}

func main() {
	// 1. 类型推断：Sum([]int{...}) 编译器从实参推断 T = int
	fmt.Println("Sum([]int):", Sum([]int{1, 2, 3}))
	fmt.Println("Sum([]float64):", Sum([]float64{1.5, 2.5}))

	// 2. ~ 约束覆盖自定义类型：Celsius 满足 ~int
	cs := []Celsius{10, 20, 30}
	fmt.Println("Sum([]Celsius):", Sum(cs), "（类型集 ~int 覆盖自定义类型）")

	// 3. 显式实例化：Sum[int] 明确指定类型参数（推断不可用或想强制时）
	fmt.Println("Sum[int] 显式实例化:", Sum[int]([]int{4, 5}))

	// 4. comparable 约束
	fmt.Println("Contains(string):", Contains([]string{"a", "b"}, "b"))

	// 5. 方法集约束 + 泛型类型
	fmt.Println("Format(Device):", Format(Device{ID: 7}))

	box := Box[string]{Value: "hello"}
	fmt.Println("Box[string].Get():", box.Get())

	// 6. 多类型参数：A 可比较（map key 语义），B 任意
	p := Pair[string, int]{K: "key", V: 42}
	fmt.Println("Pair:", p)

	// 7. 泛型与 strconv 组合：类型参数在函数内像普通类型一样用
	parse := func(s string) (int, error) { return strconv.Atoi(s) }
	if n, err := parse("123"); err == nil {
		fmt.Println("parse 123:", n)
	}
}
