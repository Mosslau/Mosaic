package main

import (
	"math"
	"testing"
)

// 测试前需先编译 C 库（见 main.go 文件头）：
//
//	cc -c -o /tmp/addvec.o c_lib/addvec.c
//	ar rcs /tmp/libaddvec.a /tmp/addvec.o
//
// 然后 CGO_ENABLED=1 go test -v ./...

func TestAddVec(t *testing.T) {
	tests := []struct {
		name string
		a, b []int32
		want []int32
	}{
		{"basic", []int32{1, 2, 3}, []int32{10, 20, 30}, []int32{11, 22, 33}},
		{"single", []int32{5}, []int32{-5}, []int32{0}},
		{"empty", []int32{}, []int32{}, []int32{}},
		{"negative", []int32{-1, -2}, []int32{1, 2}, []int32{0, 0}},
		{"large", []int32{1000000, 2000000}, []int32{3000000, 4000000}, []int32{4000000, 6000000}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := addVec(tt.a, tt.b)
			if len(got) != len(tt.want) {
				t.Fatalf("len: got %d want %d", len(got), len(tt.want))
			}
			for i := range got {
				if got[i] != tt.want[i] {
					t.Errorf("out[%d]: got %d want %d", i, got[i], tt.want[i])
				}
			}
		})
	}
}

func TestAddScalar(t *testing.T) {
	if got := addScalar(7, 8); got != 15 {
		t.Errorf("addScalar: got %d want 15", got)
	}
	if got := addScalar(-3, 3); got != 0 {
		t.Errorf("addScalar: got %d want 0", got)
	}
}

func TestSinViaC(t *testing.T) {
	got := sinViaC(math.Pi / 2)
	if math.Abs(got-1) > 1e-9 {
		t.Errorf("sin(pi/2) via C: got %v want ~1", got)
	}
	// C 的 sin 与 Go 的 math.Sin 应一致（同一 libm 语义）
	got2 := sinViaC(0.5)
	if math.Abs(got2-math.Sin(0.5)) > 1e-12 {
		t.Errorf("sin(0.5): C %v vs Go %v", got2, math.Sin(0.5))
	}
}
