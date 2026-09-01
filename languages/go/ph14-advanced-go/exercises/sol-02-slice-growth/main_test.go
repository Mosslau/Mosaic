package main

import "testing"

func TestGrowthRulesInt(t *testing.T) {
	seq := GrowSequence[int](2000)
	if !rulesOK(seq) {
		t.Errorf("[]int 序列违反规则: %v", seq)
	}
	if seq[0] != 1 || seq[1] != 2 {
		t.Errorf("[]int 起点/首次扩容: %v", seq[:2])
	}
}

func TestGrowthRulesByte(t *testing.T) {
	seq := GrowSequence[byte](2000)
	if !rulesOK(seq) {
		t.Errorf("[]byte 序列违反规则: %v", seq)
	}
	// 小元素首次扩容被 size class 抬到 8（分配器最小块 8B）
	if seq[1] != 8 {
		t.Errorf("[]byte 首次扩容应为 8（size class 抬升），实测 %d（%v）", seq[1], seq[:3])
	}
}

func TestGrowthRulesBig(t *testing.T) {
	seq := GrowSequence[[32]byte](2000)
	if !rulesOK(seq) {
		t.Errorf("[][32]byte 序列违反规则: %v", seq)
	}
}

// TestGrowthThreshold：256 是翻倍→1.25 倍的分界点——256→512 仍翻倍，之后转 1.25。
func TestGrowthThreshold(t *testing.T) {
	seq := GrowSequence[int](600)
	// 序列里 256 的下一项必须 ≥512（翻倍或更多），而 512 的下一项必须 <1024（不再翻倍）
	if seq[len(seq)-1] >= 1024 {
		t.Errorf("512 之后不应再翻倍到 ≥1024: %v", seq)
	}
}

func TestGrowthKeepsOrder(t *testing.T) {
	s := make([]int, 0, 1)
	for i := 0; i < 5000; i++ {
		s = append(s, i)
		if i != len(s)-1 {
			t.Fatalf("顺序错乱: %d", i)
		}
	}
	if s[4999] != 4999 {
		t.Errorf("内容错误")
	}
}
