package vercmp

import "testing"

func TestCompare(t *testing.T) {
	cases := []struct {
		name    string
		a, b    string
		wantCmp int
	}{
		{"带前缀相等", "go1.25.6", "1.25.6", 0},
		{"前缀不同也按数字比", "go1.25.6", "1.25.0", 1},
		{"补丁更大", "1.25.7", "1.25.6", 1},
		{"minor 更大", "1.26.0", "1.25.99", 1},
		{"major 更大", "2.0.0", "1.99.99", 1},
		{"缺段补 0", "1.25", "1.25.0", 0},
		{"缺段再比", "1.25", "1.25.6", -1},
		{"go 前缀仅一处", "1.25.6", "go1.25.7", -1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := Compare(tc.a, tc.b); got != tc.wantCmp {
				t.Fatalf("Compare(%q, %q) = %d, want %d", tc.a, tc.b, got, tc.wantCmp)
			}
		})
	}
}

func TestLess(t *testing.T) {
	if !Less("1.25.6", "1.26.0") {
		t.Fatal("Less(1.25.6, 1.26.0) 应为 true")
	}
	if Less("1.25.6", "1.25.6") {
		t.Fatal("Less(相等版本) 应为 false")
	}
}
