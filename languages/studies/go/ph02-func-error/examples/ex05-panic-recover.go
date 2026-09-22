// examples/ex05-panic-recover.go —— panic 与 recover 的边界：顶层把 panic 转为 error
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex05-panic-recover.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func riskyOperation() { panic("遇到不可恢复的内部错误") }

// safeRun 演示框架层的标准做法：recover 捕获 panic，转为 error 返回，
// 不让 panic 扩散到调用方。命名返回值 err 使 defer 能修改它。
func safeRun() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recovered from panic: %v", r)
		}
	}()
	riskyOperation()
	return nil
}

func main() {
	if err := safeRun(); err != nil {
		fmt.Println("运行失败:", err)
	} else {
		fmt.Println("运行成功")
	}
}
