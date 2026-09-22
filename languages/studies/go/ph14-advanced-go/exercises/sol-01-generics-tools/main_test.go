package main

import "testing"

func TestMap(t *testing.T) {
	if got := Map([]int{1, 2, 3}, func(v int) int { return v * 10 }); !eq(got, []int{10, 20, 30}) {
		t.Errorf("Map int: %v", got)
	}
	if got := Map([]string{"a", "b"}, func(v string) int { return len(v) }); !eq(got, []int{1, 1}) {
		t.Errorf("Map string→int: %v", got)
	}
	// 自定义类型经 ~int 约束
	if got := Map([]Celsius{10, 20}, func(v Celsius) Celsius { return v + 1 }); !eq(got, []Celsius{11, 21}) {
		t.Errorf("Map Celsius: %v", got)
	}
}

func TestFilter(t *testing.T) {
	got := Filter([]int{1, 2, 3, 4, 5}, func(v int) bool { return v%2 == 1 })
	if !eq(got, []int{1, 3, 5}) {
		t.Errorf("Filter: %v", got)
	}
	if got := Filter([]int{}, func(int) bool { return true }); len(got) != 0 {
		t.Errorf("Filter empty: %v", got)
	}
}

func TestReduce(t *testing.T) {
	if got := Reduce([]int{1, 2, 3, 4}, 0, func(a, b int) int { return a + b }); got != 10 {
		t.Errorf("Reduce sum: %d", got)
	}
	if got := Reduce([]float64{1.5, 2.5}, 0, func(a, b float64) float64 { return a + b }); got != 4.0 {
		t.Errorf("Reduce float: %v", got)
	}
	if got := Reduce([]Celsius{10, 20}, 0, func(a, b Celsius) Celsius { return a + b }); got != 30 {
		t.Errorf("Reduce Celsius: %v", got)
	}
}

func TestContains(t *testing.T) {
	if !Contains([]int{1, 2}, 2) {
		t.Error("want true")
	}
	if Contains([]string{"a"}, "b") {
		t.Error("want false")
	}
}

func eq[T comparable](a, b []T) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
