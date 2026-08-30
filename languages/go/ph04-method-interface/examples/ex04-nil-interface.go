// 来源：04-method-interface.md 第 6 章示例 4 —— nil 接口陷阱
// 一句话说明：验证「nil 接口」与「持有 nil 指针的接口」的差异，理解接口值 =（类型, 数据指针）。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run ex04-nil-interface.go
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

type Speaker interface {
	Speak() string
}

type Dog struct {
	Name string
}

// 方法内检查 nil 接收者——防御性编程
func (d *Dog) Speak() string {
	if d == nil {
		return "<nil dog 无法叫>"
	}
	return "汪汪，我是" + d.Name
}

func main() {
	// 情况 1：接口本身为 nil
	var s Speaker = nil
	fmt.Printf("nil 接口: s == nil → %v\n", s == nil) // true
	// s.Speak() // panic
	// 情况 2：接口持有 nil 指针——接口非 nil！
	var d *Dog = nil
	s = d
	fmt.Printf("持有 nil 指针: s == nil → %v\n", s == nil) // false!
	fmt.Println(s.Speak())                             // 方法可调用（Speak 内检查了 nil）
	// 情况 3：正常使用
	s = &Dog{Name: "大黄"}
	fmt.Println(s.Speak())
}
