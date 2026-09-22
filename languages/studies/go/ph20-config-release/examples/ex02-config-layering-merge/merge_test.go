// 来源：ph20-config-release examples/ex02-config-layering-merge/merge_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"reflect"
	"testing"
)

// 一棵最小配置树（键小写点路径，与 env 归一约定一致），测试用例反复使用。
func tree(port int, dark bool) map[string]any {
	return map[string]any{
		"port":     port,
		"features": map[string]any{"dark": dark, "newtelemetry": map[string]any{"percent": 0}},
		"retries":  []any{1, 2, 3},
	}
}

// mergedDefault 走真实 pipeline 第一步：default 层合入空 map，叶子来源全记 trace。
func mergedDefault() (map[string]any, Trace) {
	merged := map[string]any{}
	trace := Trace{}
	MergeInto(merged, tree(8080, false), SourceDefault, trace)
	return merged, trace
}

func TestMergeFileOverridesDefaultLeafByLeaf(t *testing.T) {
	merged, trace := mergedDefault()
	// file 层只给了 features.dark：只覆盖该叶子，其余保持 default。
	MergeInto(merged, map[string]any{"features": map[string]any{"dark": true}}, SourceFile, trace)

	if got := merged["features"].(map[string]any)["dark"]; got != true {
		t.Errorf("features.dark = %v, want true（被 file 覆盖）", got)
	}
	if got := trace["features.dark"]; got != SourceFile {
		t.Errorf("features.dark 来源 = %q, want %q", got, SourceFile)
	}
	// 同层其它子键不被波及：字段级覆盖，而非整层替换。
	if got := merged["features"].(map[string]any)["newtelemetry"].(map[string]any)["percent"]; got != 0 {
		t.Errorf("features.newtelemetry.percent = %v, want 0（未被 file 触碰）", got)
	}
	if got := trace["features.newtelemetry.percent"]; got != SourceDefault {
		t.Errorf("features.newtelemetry.percent 来源 = %q, want %q", got, SourceDefault)
	}
	if got := merged["port"]; got != 8080 {
		t.Errorf("port = %v, want 8080（file 层没给 port）", got)
	}
}

func TestArrayIsWholeReplacementNotElementMerge(t *testing.T) {
	merged := tree(8080, false)
	trace := Trace{}
	MergeInto(merged, map[string]any{"retries": []any{5}}, SourceFile, trace)

	// 数组不能"逐元素合并"（[1 2 3] + [5] ≠ [1 2 3 5]），整替换才可预期。
	want := []any{5}
	if got := merged["retries"]; !reflect.DeepEqual(got, want) {
		t.Errorf("retries = %v, want %v（数组整替换）", got, want)
	}
	if got := trace["retries"]; got != SourceFile {
		t.Errorf("retries 来源 = %q, want %q", got, SourceFile)
	}
}

func TestApplyDottedCoercesByTargetType(t *testing.T) {
	merged := tree(8080, false)
	trace := Trace{}

	// env 给出字符串 "7070"，叶子是 int → 转成 int。
	if err := ApplyDotted(merged, "port", "7070", SourceEnv, trace); err != nil {
		t.Fatalf("ApplyDotted(port): %v", err)
	}
	if got, ok := merged["port"].(int); !ok || got != 7070 {
		t.Errorf("port = %#v, want int(7070)（按现有类型 int 解析）", merged["port"])
	}
	if got := trace["port"]; got != SourceEnv {
		t.Errorf("port 来源 = %q, want %q", got, SourceEnv)
	}

	// bool 叶子："true" 字符串 → bool(true)。
	if err := ApplyDotted(merged, "features.dark", "true", SourceEnv, trace); err != nil {
		t.Fatalf("ApplyDotted(dark): %v", err)
	}
	if got := merged["features"].(map[string]any)["dark"]; got != true {
		t.Errorf("features.dark = %v, want true", got)
	}
}

func TestApplyDottedTypeMismatchRejected(t *testing.T) {
	merged := tree(8080, false)
	// bool 叶子给 "7070"：解析失败，error 带上下文而非悄悄存字符串。
	err := ApplyDotted(merged, "features.dark", "7070", SourceEnv, Trace{})
	if err == nil {
		t.Fatal("bool 叶子给非 bool 字符串应当报错")
	}
	if merged["features"].(map[string]any)["dark"] != false {
		t.Errorf("失败后叶子不应被污染，got %v", merged["features"].(map[string]any)["dark"])
	}
}

func TestApplyDottedUnknownKeyRejected(t *testing.T) {
	merged := tree(8080, false)
	// 拼写错误：FEATURES__DARKT 转成 features.darkt —— 树上没有这个键，必须拒绝，
	// 防止"改了个寂寞"（配置没生效还没人知道）。
	err := ApplyDotted(merged, "features.darkt", "true", SourceEnv, Trace{})
	if !errors.Is(err, ErrUnknownKey) {
		t.Fatalf("期望 ErrUnknownKey，got %v", err)
	}
}

func TestApplyDottedCompositeValueRejected(t *testing.T) {
	merged := tree(8080, false)
	// 目标是 features（map）：env 是字符串，不能整替换复合值。
	err := ApplyDotted(merged, "features", "x", SourceEnv, Trace{})
	if !errors.Is(err, ErrNotReplaceable) {
		t.Fatalf("期望 ErrNotReplaceable，got %v", err)
	}
}

func TestFullPipelinePrecedence(t *testing.T) {
	// 完整流水线：default → file → env → flag，验证 per-key last-wins。
	trace := Trace{}
	merged := map[string]any{}
	dt, _ := decodeJSONTree([]byte(defaultJSON))
	MergeInto(merged, dt, SourceDefault, trace)
	ft, _ := decodeJSONTree([]byte(devConfigJSON))
	MergeInto(merged, ft, SourceFile, trace)

	apply := func(dotted, raw string) {
		if err := ApplyDotted(merged, dotted, raw, SourceEnv, trace); err != nil {
			t.Fatalf("apply %s: %v", dotted, err)
		}
	}
	apply("port", "7070")
	apply("features.newtelemetry.percent", "10")

	// flag 覆盖 port。
	if err := ApplyDotted(merged, "port", "6060", SourceFlag, trace); err != nil {
		t.Fatalf("flag port: %v", err)
	}

	cases := []struct {
		key  string
		want any
		src  string
	}{
		{"port", 6060, SourceFlag},                              // flag > env > file > default
		{"features.dark", true, SourceFile},                     // file 覆盖 default，env/flag 未碰
		{"features.newtelemetry.percent", 10, SourceEnv},        // env 覆盖 default，仅此叶
		{"features.newtelemetry.enabled", false, SourceDefault}, // default 兜底
		{"service.name", "fleet-api", SourceDefault},            // 未参与各层
		{"retries", []any{5}, SourceFile},                       // 数组整替换
	}
	for _, c := range cases {
		if got := trace[c.key]; got != c.src {
			t.Errorf("%s 来源 = %q, want %q", c.key, got, c.src)
		}
	}
	gotPort := merged["port"]
	if gotPort != 6060 {
		t.Errorf("port = %v, want 6060", gotPort)
	}
}
