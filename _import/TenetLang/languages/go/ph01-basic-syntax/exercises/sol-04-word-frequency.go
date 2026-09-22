// exercises/sol-04-word-frequency.go —— 练习 4 参考实现：map 统计词频并按次数降序输出
// 对应 exercises/README.md 练习 4
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run sol-04-word-frequency.go
// 已验证：go vet 通过，gofmt 无差异；输出按次数降序 apple: 3 / banana: 2 / orange: 1
package main

import (
	"fmt"
	"sort"
	"strings"
)

// wordCount 用于把 map 转成切片后排序
type wordCount struct {
	word  string
	count int
}

func main() {
	text := "apple banana apple orange banana apple"
	words := strings.Fields(text)

	// 1. 用 map 计数
	freq := make(map[string]int)
	for _, w := range words {
		freq[w]++
	}

	// 2. map 转成切片以便排序
	counts := make([]wordCount, 0, len(freq))
	for w, c := range freq {
		counts = append(counts, wordCount{word: w, count: c})
	}

	// 3. 按次数降序；次数相同按字典序，保证输出稳定
	sort.Slice(counts, func(i, j int) bool {
		if counts[i].count != counts[j].count {
			return counts[i].count > counts[j].count
		}
		return counts[i].word < counts[j].word
	})

	for _, wc := range counts {
		fmt.Printf("%s: %d\n", wc.word, wc.count)
	}
}
