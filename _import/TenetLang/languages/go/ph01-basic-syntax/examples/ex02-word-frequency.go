// examples/ex02-word-frequency.go —— 词频统计：用 map 统计一段文本中各单词出现次数
// 对应主文档 languages/go/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 2
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run ex02-word-frequency.go
// 已验证：go vet 通过，gofmt 无差异；输出 apple: 3 / banana: 2 / orange: 1（顺序随机，map 遍历无序）
package main

import (
	"fmt"
	"strings"
)

func main() {
	text := "apple banana apple orange banana apple"
	words := strings.Fields(text)

	freq := make(map[string]int)
	for _, w := range words {
		freq[w]++
	}

	for word, count := range freq {
		fmt.Printf("%s: %d\n", word, count)
	}
}
