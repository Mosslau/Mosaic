// 来源：ph08-testing 主文档 3.8 节与示例 6 —— fuzz testing + Example 文档示例
// 一句话说明：单词计数函数，空白定义与 strings.Fields 保持一致。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go run .
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"unicode"
)

// WordCount 统计单词数：连续空白为分隔符（与 strings.Fields 定义一致）
func WordCount(s string) int {
	count := 0
	inWord := false
	for _, r := range s {
		if unicode.IsSpace(r) {
			inWord = false
		} else if !inWord {
			count++
			inWord = true
		}
	}
	return count
}

func main() {
	fmt.Println(WordCount("hello world"))
}
