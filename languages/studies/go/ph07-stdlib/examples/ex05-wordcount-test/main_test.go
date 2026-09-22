// 来源：07-stdlib.md 第 6 章示例 5 —— 表驱动测试：数据与期望并列成表，t.Run 拆成子测试
// 一句话说明：go test -v 运行，go test -run 'TestWordCount/多行' 可单独筛选子测试。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go test -v
//
// 验证状态：已验证（Go 1.22.2）
package main

import "testing"

func TestWordCount(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want int
	}{
		{"空串", "", 0},
		{"单单词", "hello", 1},
		{"多空格", "  hello   go  ", 2},
		{"多行", "a b\nc", 3},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := WordCount(tc.in); got != tc.want {
				t.Errorf("WordCount(%q) = %d, 期望 %d", tc.in, got, tc.want)
			}
		})
	}
}
