// 来源：ph15-version-toolchain 示例 2 —— 语义化版本比较（模块版本排序规则）
// 一句话说明：go 工具按语义化版本（semver）给模块版本排序——v1.9.0 < v1.10.0
// 必须按数字段比较（字典序会把 v1.10.0 排到 v1.9.0 前面，是常见错误）。本文件
// 实现教学性子集：可选 v 前缀、MAJOR.MINOR.PATCH 数字比较（缺段补 0）、预发布
// 版本（-alpha/-beta/-rc）排序、构建元数据（+xxx，含 Go 的 +incompatible）
// 不参与排序。生产环境请用官方扩展包 golang.org/x/mod/semver（本仓库不引第三方
// 依赖，自实现并保持规则一致）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"fmt"
	"strconv"
	"strings"
)

// version 是解析后的三元组 + 预发布/构建元数据。
type version struct {
	major, minor, patch int
	pre                 string // 预发布标识串（不含 '-'）；空 = 正式版
	hasPre              bool
}

// Compare 比较两个模块版本（允许带或不带 v 前缀）。返回 -1 / 0 / 1。
func Compare(a, b string) int {
	pa, pb := parse(a), parse(b)
	if pa.major != pb.major {
		return cmpInt(pa.major, pb.major)
	}
	if pa.minor != pb.minor {
		return cmpInt(pa.minor, pb.minor)
	}
	if pa.patch != pb.patch {
		return cmpInt(pa.patch, pb.patch)
	}
	return comparePre(pa, pb)
}

// parse 去掉 v 前缀后拆出 core / prerelease / build（build 被忽略）。
func parse(s string) version {
	s = strings.TrimPrefix(s, "v")
	if i := strings.IndexByte(s, '+'); i >= 0 {
		s = s[:i] // 丢弃 "+" 后缀元数据（如 +incompatible）：不参与排序
	}
	v := version{}
	if i := strings.IndexByte(s, '-'); i >= 0 {
		v.pre, v.hasPre = s[i+1:], true
		s = s[:i]
	}
	segs := strings.Split(s, ".")
	v.major = atoi(segs[0])
	if len(segs) > 1 {
		v.minor = atoi(segs[1])
	}
	if len(segs) > 2 {
		v.patch = atoi(segs[2])
	}
	// 缺段补 0：v1.2 == v1.2.0
	return v
}

func atoi(s string) int {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0
	}
	return n
}

// comparePre：正式版 > 任何预发布版；预发布标识按 '.' 分段比较，
// 数值标识按数值比较、字母标识按字典序，且数值标识 < 字母标识。
func comparePre(a, b version) int {
	switch {
	case !a.hasPre && !b.hasPre:
		return 0
	case !a.hasPre:
		return 1 // 1.2.3 > 1.2.3-rc.1
	case !b.hasPre:
		return -1
	}
	ai, bi := strings.Split(a.pre, "."), strings.Split(b.pre, ".")
	for i := 0; i < len(ai) && i < len(bi); i++ {
		if c := cmpPreIdent(ai[i], bi[i]); c != 0 {
			return c
		}
	}
	switch {
	case len(ai) < len(bi):
		return -1 // 1.0.0-alpha < 1.0.0-alpha.1（更长 = 更晚）
	case len(ai) > len(bi):
		return 1
	}
	return 0
}

// cmpPreIdent：全数字按数值比；数值 < 字母；字母按字典序。
func cmpPreIdent(x, y string) int {
	nx, ny := isNum(x), isNum(y)
	switch {
	case nx && ny:
		return cmpInt(atoi(x), atoi(y))
	case nx:
		return -1 // 数值标识 < 字母标识（semver 规则）
	case ny:
		return 1
	default:
		return strings.Compare(x, y)
	}
}

func isNum(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

func cmpInt(a, b int) int {
	switch {
	case a < b:
		return -1
	case a > b:
		return 1
	}
	return 0
}

func main() {
	cases := []struct {
		a, b string
	}{
		{"v1.9.0", "v1.10.0"}, // 数字段比较：1.9 < 1.10
		{"v1.10.0", "v1.9.0"},
		{"v1.2.3", "v2.0.0"},              // major 不同：2 > 1
		{"v1.2", "v1.2.1"},                // 缺段补 0：1.2 == 1.2.0 < 1.2.1
		{"v1.2.3-rc.1", "v1.2.3"},         // 预发布 < 正式版
		{"v1.2.3-alpha", "v1.2.3-beta"},   // 字母标识按字典序
		{"v1.2.3-1", "v1.2.3-alpha"},      // 数值标识 < 字母标识
		{"v1.2.3+incompatible", "v1.2.3"}, // 构建元数据不参与排序
	}
	for _, c := range cases {
		fmt.Printf("Compare(%q, %q) = %d\n", c.a, c.b, Compare(c.a, c.b))
	}
	fmt.Println("结论: 数字段数值比较; 缺段补 0; 预发布 < 正式版; +build 忽略")
}
