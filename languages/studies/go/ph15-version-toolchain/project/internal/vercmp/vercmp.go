// Package vercmp 提供 Go 工具链版本的数值比较。
// 形如 "go1.25.6"（toolchain 行 / runtime.Version()）与 "1.25.0"（go 行），
// 均去掉可选 go 前缀后按数字段比较、缺段补 0（1.25 == 1.25.0）。
// 这是 x/mod/semver 之外的一个简化规则：Go 工具自身的版本比较按同样的
// 数字段思路实现（本文档 4.1 节有说明），本包只覆盖发布版（无 rc/beta 后缀）。
package vercmp

import (
	"strconv"
	"strings"
)

// Compare 比较两个 Go 版本串，返回 -1 / 0 / 1。
func Compare(a, b string) int {
	as := segments(a)
	bs := segments(b)
	n := len(as)
	if len(bs) > n {
		n = len(bs)
	}
	for i := 0; i < n; i++ {
		av, bv := 0, 0
		if i < len(as) {
			av, _ = strconv.Atoi(as[i])
		}
		if i < len(bs) {
			bv, _ = strconv.Atoi(bs[i])
		}
		if av != bv {
			if av < bv {
				return -1
			}
			return 1
		}
	}
	return 0
}

// Less 是 a < b 的便捷包装。
func Less(a, b string) bool { return Compare(a, b) < 0 }

// segments 去掉 go 前缀并按 '.' 拆分。
func segments(v string) []string {
	return strings.Split(strings.TrimPrefix(v, "go"), ".")
}
