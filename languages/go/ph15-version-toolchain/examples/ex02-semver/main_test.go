package main

import "testing"

func TestCompare(t *testing.T) {
	cases := []struct {
		name string
		a, b string
		want int
	}{
		{"v 前缀等价", "v1.2.3", "1.2.3", 0},
		{"数值比较非字典序", "v1.9.0", "v1.10.0", -1},
		{"反向", "v1.10.0", "v1.9.0", 1},
		{"major 优先", "v1.2.3", "v2.0.0", -1},
		{"minor 优先", "v1.2.3", "v1.3.0", -1},
		{"patch 优先", "v1.2.3", "v1.2.4", -1},
		{"缺段补 0", "v1.2", "v1.2.0", 0},
		{"缺段补 0 再比较", "v1.2", "v1.2.1", -1},
		{"预发布 < 正式版", "v1.2.3-rc.1", "v1.2.3", -1},
		{"正式版 > 预发布", "v1.2.3", "v1.2.3-beta", 1},
		{"字母标识字典序", "v1.2.3-alpha", "v1.2.3-beta", -1},
		{"rc 晚于 beta", "v1.2.3-beta", "v1.2.3-rc.1", -1},
		{"数值标识 < 字母标识", "v1.2.3-1", "v1.2.3-alpha", -1},
		{"预发布分段前缀", "v1.2.3-alpha", "v1.2.3-alpha.1", -1},
		{"build 元数据忽略", "v1.2.3+incompatible", "v1.2.3", 0},
		{"build 元数据忽略 2", "v1.2.3+meta", "v1.2.3+other", 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := Compare(tc.a, tc.b); got != tc.want {
				t.Fatalf("Compare(%q, %q) = %d, want %d", tc.a, tc.b, got, tc.want)
			}
		})
	}
}
