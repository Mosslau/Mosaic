// examples/ex03-map-ops.go —— Map 安全操作（ok 模式）、删除与遍历
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex03-map-ops.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func main() {
	// make 初始化（字面量 nil 不可写）
	cache := make(map[string]int)
	cache["cpu"] = 45
	cache["mem"] = 72

	// 安全查询：ok 模式判断 key 是否存在
	keys := []string{"cpu", "disk", "mem"}
	for _, k := range keys {
		if v, ok := cache[k]; ok {
			fmt.Printf("%s=%d\n", k, v)
		} else {
			fmt.Printf("%s: not found\n", k)
		}
	}

	// 删除后查询
	delete(cache, "mem")
	if _, ok := cache["mem"]; !ok {
		fmt.Println("mem 已删除")
	}

	// 遍历——多次运行输出顺序可能不同
	cache["gpu"] = 20
	cache["net"] = 10
	fmt.Println("\n所有条目:")
	for k, v := range cache {
		fmt.Printf("  %s: %d\n", k, v)
	}
}
