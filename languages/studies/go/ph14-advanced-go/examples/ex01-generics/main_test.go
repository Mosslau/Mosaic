package main

import "testing"

// ---- 类型集约束：Sum 覆盖 int / float64 / 自定义类型 ----

func TestSum(t *testing.T) {
	tests := []struct {
		name string
		got  any
		want any
	}{
		{"int", Sum([]int{1, 2, 3}), 6},
		{"float64", Sum([]float64{1.5, 2.5}), 4.0},
		{"custom ~int", Sum([]Celsius{10, 20}), Celsius(30)},
		{"empty", Sum([]int{}), 0},
	}
	for _, tt := range tests {
		if tt.got != tt.want {
			t.Errorf("%s: got %v, want %v", tt.name, tt.got, tt.want)
		}
	}
}

// ---- comparable 约束 ----

func TestContains(t *testing.T) {
	if !Contains([]string{"a", "b", "c"}, "b") {
		t.Error("want b in [a b c]")
	}
	if Contains([]string{"a", "b"}, "z") {
		t.Error("want z not in [a b]")
	}
	if !Contains([]int{1, 2}, 2) {
		t.Error("want 2 in [1 2]")
	}
}

// ---- 方法集约束 + 泛型类型 ----

func TestFormat(t *testing.T) {
	if got := Format(Device{ID: 7}); got != "device-7" {
		t.Errorf("Format: got %q, want %q", got, "device-7")
	}
}

func TestBoxAndPair(t *testing.T) {
	b := Box[int]{Value: 9}
	if b.Get() != 9 {
		t.Errorf("Box.Get: got %d", b.Get())
	}
	p := Pair[string, int]{K: "k", V: 1}
	if p.K != "k" || p.V != 1 {
		t.Errorf("Pair: %+v", p)
	}
}
