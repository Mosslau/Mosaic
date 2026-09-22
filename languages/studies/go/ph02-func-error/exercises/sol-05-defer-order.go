// exercises/sol-05-defer-order.go —— 练习 5 参考实现：defer 顺序与参数求值
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-05-defer-order.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func main() {
	i := 0

	// defer 的参数在注册时立即求值：这里捕获的是 i=0
	defer fmt.Println("defer 带参数:", i)

	// defer 闭包不带参数，引用的是变量本身：执行时读到的是最终值
	defer func() {
		fmt.Println("defer 闭包引用:", i)
	}()

	// LIFO：后注册的先执行
	defer fmt.Println("defer 最先注册")

	i = 100
	fmt.Println("main 结束:", i)
	// 执行顺序：main 结束 -> defer 最先注册 -> defer 闭包引用 -> defer 带参数
}
