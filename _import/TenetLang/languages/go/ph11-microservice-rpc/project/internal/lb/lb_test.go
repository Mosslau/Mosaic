package lb

import "testing"

func TestRoundRobinSequence(t *testing.T) {
	rr := New([]string{"A", "B", "C"})
	want := []string{"A", "B", "C", "A", "B", "C"}
	for i, w := range want {
		if got := rr.Pick(); got != w {
			t.Fatalf("pick#%d = %q, want %q", i+1, got, w)
		}
	}
}

func TestRoundRobinEmpty(t *testing.T) {
	rr := New(nil)
	if got := rr.Pick(); got != "" {
		t.Fatalf("空列表 Pick 应为空串, got %q", got)
	}
	if rr.Size() != 0 {
		t.Fatalf("Size 应为 0, got %d", rr.Size())
	}
}

func TestRoundRobinDoesNotShareState(t *testing.T) {
	// New 应复制地址切片：外部修改原切片不影响均衡器
	src := []string{"A", "B"}
	rr := New(src)
	src[0] = "X"
	if got := rr.Pick(); got != "A" {
		t.Fatalf("应使用复制的列表, got %q", got)
	}
}

func TestAddrsCopy(t *testing.T) {
	rr := New([]string{"A", "B"})
	got := rr.Addrs()
	if len(got) != 2 || got[0] != "A" || got[1] != "B" {
		t.Fatalf("Addrs 异常: %v", got)
	}
	// 返回的是副本：外部修改不影响均衡器
	got[0] = "X"
	if rr.Pick() != "A" {
		t.Fatal("Addrs 应返回副本")
	}
}
