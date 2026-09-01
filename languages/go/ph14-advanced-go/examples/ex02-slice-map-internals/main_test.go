package main

import (
	"sync"
	"testing"
)

// ---- slice 扩容的结构性规则（跨机器可移植的断言）----
// 精确数字（如 512→848）依赖架构与 size class，见 README 实测；这里断言规则本身：
// ① 小容量翻倍（<256）；② 大容量按 ~1.25 增长；③ 容量只增不减且 ≥ len。

// growthRulesOK 断言扩容的结构性规则（跨机器可移植，不绑定具体 size class）：
// ① 容量严格增长；② prev<256 时翻倍（cur ≥ 2×prev，size class 只会向上取整）；
// ③ prev≥256 时按 ~1.25 增长后向上取整，比率落在 [1.25, 2) 内。
// 精确数字（512→848 之类）依赖元素大小与分配器 size class，见 README 实测表。
func growthRulesOK(seq []int) bool {
	for i := 1; i < len(seq); i++ {
		prev, cur := seq[i-1], seq[i]
		if cur <= prev {
			return false // 容量必须严格增长
		}
		if prev < 256 {
			if cur < prev*2 {
				return false // 翻倍（小元素首轮会被 size class 抬得更高，只断言下界）
			}
		} else {
			if cur < prev*5/4 || cur > prev*2 {
				return false // ~1.25 增长 + 向上取整，不会超过翻倍
			}
		}
	}
	return true
}

func TestIntGrowthRules(t *testing.T) {
	seq := IntGrowth(2000)
	if !growthRulesOK(seq) {
		t.Errorf("[]int 扩容序列违反规则: %v", seq)
	}
	if seq[1] != 2 {
		t.Errorf("[]int 首次扩容应为 2，实测 %d（序列 %v）", seq[1], seq)
	}
}

func TestByteGrowthRules(t *testing.T) {
	seq := ByteGrowth(2000)
	if !growthRulesOK(seq) {
		t.Errorf("[]byte 扩容序列违反规则: %v", seq)
	}
	// 小元素时 size class 直接抬到 8（分配器最小 8 字节块）
	if seq[1] != 8 {
		t.Errorf("[]byte 首次扩容应为 8（size class 抬升），实测 %d（序列 %v）", seq[1], seq)
	}
}

func TestBigGrowthRules(t *testing.T) {
	seq := BigGrowth(2000)
	if !growthRulesOK(seq) {
		t.Errorf("[][32]byte 扩容序列违反规则: %v", seq)
	}
	if seq[1] != 2 {
		t.Errorf("[][32]byte 首次扩容应为 2，实测 %d", seq[1])
	}
}

func TestAppendResult(t *testing.T) {
	s := make([]int, 0, 1)
	for i := 0; i < 1000; i++ {
		s = append(s, i)
	}
	if len(s) != 1000 || s[999] != 999 {
		t.Errorf("append 结果错误: len=%d", len(s))
	}
}

// ---- map 行为 ----

func TestMapBasics(t *testing.T) {
	m := map[string]int{"a": 1, "b": 2}
	if v, ok := m["a"]; !ok || v != 1 {
		t.Error("读 a 应得 1")
	}
	if _, ok := m["z"]; ok {
		t.Error("z 不应存在")
	}
	delete(m, "a")
	if _, ok := m["a"]; ok {
		t.Error("删除后 a 不应存在")
	}
	if len(m) != 1 {
		t.Errorf("len 应 1，实测 %d", len(m))
	}
}

// TestConcurrentSafeMap：加锁并发写 —— -race 必须零报告
func TestConcurrentSafeMap(t *testing.T) {
	m := make(map[int]int)
	var mu sync.Mutex
	var wg sync.WaitGroup
	for g := 0; g < 4; g++ {
		wg.Add(1)
		go safeWrite(&wg, m, &mu, g)
	}
	wg.Wait()
	if len(m) != 4000 {
		t.Errorf("加锁并发写后 len 应 4000，实测 %d", len(m))
	}
}
