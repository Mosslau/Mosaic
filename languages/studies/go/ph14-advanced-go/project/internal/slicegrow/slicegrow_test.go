package slicegrow

import "testing"

func TestRulesInt(t *testing.T) {
	seq := GrowSequence[int](2000)
	if !RulesOK(seq) {
		t.Errorf("[]int 违反规则: %v", seq)
	}
	if seq[0] != 1 || seq[1] != 2 {
		t.Errorf("起点/首次扩容: %v", seq[:2])
	}
}

func TestRulesByte(t *testing.T) {
	seq := GrowSequence[byte](2000)
	if !RulesOK(seq) {
		t.Errorf("[]byte 违反规则: %v", seq)
	}
	if seq[1] != 8 {
		t.Errorf("[]byte 首轮应被 size class 抬到 8: %v", seq[:3])
	}
}

func TestRulesBig(t *testing.T) {
	seq := GrowSequence[[32]byte](2000)
	if !RulesOK(seq) {
		t.Errorf("[][32]byte 违反规则: %v", seq)
	}
}

// TestThreshold：256 是翻倍→1.25 的分界点，512 之后不再翻倍。
func TestThreshold(t *testing.T) {
	seq := GrowSequence[int](600)
	last := seq[len(seq)-1]
	if last >= 1024 {
		t.Errorf("512 之后不应翻倍到 ≥1024: %v", seq)
	}
}

// TestContentIntegrity：append 的内容与顺序不因扩容丢失。
func TestContentIntegrity(t *testing.T) {
	s := make([]int, 0, 1)
	for i := 0; i < 10000; i++ {
		s = append(s, i)
	}
	if len(s) != 10000 {
		t.Fatalf("len: %d", len(s))
	}
	for i, v := range s {
		if v != i {
			t.Fatalf("s[%d]=%d", i, v)
		}
	}
}
