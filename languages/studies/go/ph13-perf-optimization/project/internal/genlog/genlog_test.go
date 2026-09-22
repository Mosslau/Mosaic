package genlog

import (
	"encoding/json"
	"testing"
)

// 生成的行必须是合法 JSON 且含三个解析字段
func TestLineValidJSON(t *testing.T) {
	lines := Generate(200)
	for i, line := range lines {
		if !json.Valid([]byte(line)) {
			t.Fatalf("第 %d 行不是合法 JSON: %s", i, line)
		}
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			t.Fatalf("第 %d 行解析失败: %v", i, err)
		}
		for _, k := range []string{"level", "device_id", "latency_ms"} {
			if _, ok := m[k]; !ok {
				t.Fatalf("第 %d 行缺字段 %s: %s", i, k, line)
			}
		}
	}
}

// 固定种子：两次生成必须逐行一致（基准与验收可复现的前提）
func TestDeterministic(t *testing.T) {
	a, b := Generate(100), Generate(100)
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("第 %d 行不一致（Generate 应可复现）:\n%s\n%s", i, a[i], b[i])
		}
	}
}
