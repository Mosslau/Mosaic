// examples/ex04-cli-validator.go —— 命令行参数校验：函数类型 + 闭包 + 可变参数 + 错误聚合
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex04-cli-validator.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"strconv"
)

// Validator 是单方法场景下的函数类型，比定义接口更轻量
type Validator func(value string) error

// required 返回一个闭包，捕获字段名
func required(field string) Validator {
	return func(value string) error {
		if value == "" {
			return fmt.Errorf("field %q is required", field)
		}
		return nil
	}
}

// intRange 返回一个闭包，捕获字段名与取值范围
func intRange(field string, min, max int) Validator {
	return func(value string) error {
		n, err := strconv.Atoi(value)
		if err != nil {
			return fmt.Errorf("field %q must be integer: %w", field, err)
		}
		if n < min || n > max {
			return fmt.Errorf("field %q must be between %d and %d", field, min, max)
		}
		return nil
	}
}

// validate 用可变参数接收任意多个校验器，聚合全部错误而非遇到第一个就返回
func validate(value string, validators ...Validator) []error {
	var errs []error
	for _, v := range validators {
		if err := v(value); err != nil {
			errs = append(errs, err)
		}
	}
	return errs
}

func main() {
	params := map[string]string{"port": "8080", "timeout": "abc"}
	if errs := validate(params["port"], required("port"), intRange("port", 1, 65535)); len(errs) > 0 {
		fmt.Println("port 校验失败:")
		for _, err := range errs {
			fmt.Println("  -", err)
		}
	}
	if errs := validate(params["timeout"], required("timeout"), intRange("timeout", 1, 300)); len(errs) > 0 {
		fmt.Println("timeout 校验失败:")
		for _, err := range errs {
			fmt.Println("  -", err)
		}
	}
}
