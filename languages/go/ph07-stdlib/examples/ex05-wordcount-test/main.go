// 来源：07-stdlib.md 第 6 章示例 5 —— 被测代码（单词统计）
// 一句话说明：WordCount 统计文本单词数，供 main_test.go 表驱动测试。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

// WordCount 统计一段文本的单词数
func WordCount(s string) int {
	count := 0
	inWord := false
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' {
			inWord = false
		} else if !inWord {
			count++
			inWord = true
		}
	}
	return count
}

func main() { fmt.Println("单词数:", WordCount("hello go stdlib")) }
