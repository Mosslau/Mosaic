// 来源：ph08-testing 主文档 3.8 节与示例 6 —— fuzz testing + Example 文档示例
// 一句话说明：fuzz 断言不变量（与 strings.Fields 结果一致）；Example 兼具文档与测试。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...                                # 普通测试（含种子语料与 Example 输出比对）
//	go test -fuzz=FuzzWordCount -fuzztime=10s ./... # 真 fuzz 10 秒
//
// 验证状态：已验证（go1.25.6，含 10 秒 fuzz 无失败）
package main

import (
	"fmt"
	"strings"
	"testing"
)

func FuzzWordCount(f *testing.F) {
	f.Add("hello world") // 种子语料：从正常输入出发
	f.Add("  多空格  a\tb\n")
	f.Fuzz(func(t *testing.T, s string) {
		if got := WordCount(s); got != len(strings.Fields(s)) {
			t.Errorf("WordCount(%q) = %d, strings.Fields 给出 %d", s, got, len(strings.Fields(s)))
		}
	})
}

// ExampleWordCount 是"会被 go test 执行"的文档示例：
// // Output: 注释必须与实际输出逐字符一致
func ExampleWordCount() {
	fmt.Println(WordCount("hello world"))
	// Output: 2
}
