// examples/ex01-safe-divide.go —— 安全除法：多返回值与 errors.New
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex01-safe-divide.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
)

func divide(a, b int) (int, error) {
	if b == 0 {
		return 0, errors.New("divide by zero")
	}
	return a / b, nil
}

func main() {
	if result, err := divide(10, 3); err != nil {
		fmt.Println("错误:", err)
	} else {
		fmt.Println("10 / 3 =", result)
	}
	if _, err := divide(5, 0); err != nil {
		fmt.Println("错误:", err)
	}
}
