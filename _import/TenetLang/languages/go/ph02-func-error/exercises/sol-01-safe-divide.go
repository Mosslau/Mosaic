// exercises/sol-01-safe-divide.go —— 练习 1 参考实现：安全除法
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-01-safe-divide.go
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
	if q, err := divide(10, 3); err != nil {
		fmt.Println("错误:", err)
	} else {
		fmt.Println("10 / 3 =", q)
	}
	if _, err := divide(5, 0); err != nil {
		fmt.Println("错误:", err)
	}
}
