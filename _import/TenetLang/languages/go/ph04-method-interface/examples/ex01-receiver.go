// 来源：04-method-interface.md 第 6 章示例 1 —— 值接收者与指针接收者对比
// 一句话说明：演示值接收者操作副本、指针接收者操作原值的方法集差异。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run ex01-receiver.go
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

type Counter struct {
	Count int
}

// 值接收者：操作副本
func (c Counter) ValueInc() {
	c.Count++ // 修改副本，不影响原值
}

// 指针接收者：修改原值
func (c *Counter) PtrInc() {
	c.Count++ // 修改原值
}

func main() {
	c := Counter{Count: 0}
	c.ValueInc()
	fmt.Println("ValueInc 后:", c.Count) // 0
	c.PtrInc()
	fmt.Println("PtrInc 后:  ", c.Count) // 1
	Counter{Count: 10}.ValueInc()       // 字面量可调用值接收者
	// Counter{Count: 10}.PtrInc() // 编译错误：字面量不可寻址
}
