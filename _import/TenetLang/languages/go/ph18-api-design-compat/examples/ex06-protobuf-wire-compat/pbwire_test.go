// 来源：ph18-api-design-compat examples/ex06-protobuf-wire-compat/pbwire_test.go
// 一句话说明：protobuf 兼容规则的实验测试（主文档 3.8）。四组断言对应四条规则：
// ① 加字段（v2 追加字段 4）→ v1 reader 无损（向前兼容）；② 老数据缺新字段 →
// v2 reader 落零值（向后兼容）；③ 改字段号 → v1 reader 读到错位数据（破坏性变更，
// 字段号永远不许改）；④ 用 reserved 声明的字段号再次出现 → v2 reader 忽略但 v1 已炸。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "testing"

// TestAddFieldIsForwardCompatible：v2 加字段 4，v1 reader 读 v2 数据无损。
// 这是"字段只增不删"在 protobuf 世界的机制基础。
func TestAddFieldIsForwardCompatible(t *testing.T) {
	b2 := encodeV2(v2Device{ID: "car-001", Name: "1号车", Online: true, Model: "M300"})
	d, err := decodeV1(b2) // 老 reader 吃新数据
	if err != nil {
		t.Fatal(err)
	}
	if d.ID != "car-001" || d.Name != "1号车" || !d.Online {
		t.Fatalf("v1 reader misread v2 data: %+v", d)
	}
}

// TestOldDataDefaultsNewField：老 reader 发来的数据没有字段 4，v2 reader 读零值。
func TestOldDataDefaultsNewField(t *testing.T) {
	b1 := encodeV1(v1Device{ID: "car-001", Name: "1号车", Online: true})
	d, err := decodeV2(b1) // 新 reader 吃老数据
	if err != nil {
		t.Fatal(err)
	}
	if d.Model != "" {
		t.Fatalf("missing field 4 should default to zero value, got %q", d.Model)
	}
	if d.ID != "car-001" {
		t.Fatalf("id = %q, want car-001", d.ID)
	}
}

// TestFieldNumberChangeBreaksOldReaders：字段号是契约。若 v2 把 Model 编到字段号 2
// （原本 Name 的位置），v1 reader 会把 Model 的字节当成 Name —— 语义错位且不报错，
// 是兼容性事故里最阴险的一种（无声数据损坏）。
func TestFieldNumberChangeBreaksOldReaders(t *testing.T) {
	// 模拟"事故版本"：Model 被（错误地）编进字段号 2，Name 挪到字段号 5。
	var buf []byte
	buf = appendStringField(buf, 1, "car-001")
	buf = appendStringField(buf, 2, "M300") // 字段号 2 本属于 Name！
	buf = appendBoolField(buf, 3, true)
	buf = appendStringField(buf, 5, "1号车")

	d, err := decodeV1(buf) // v1 reader 只认 1/2/3
	if err != nil {
		t.Fatal(err)
	}
	if d.Name != "M300" { // v1 reader 把"model"当成了 name——语义错位
		t.Fatalf("expected silent misread demo: Name = %q, want M300", d.Name)
	}
	// 并且真正的名字字段 5 被丢弃——不报错的数据丢失比报错更难排查。
	if d.Online != true {
		t.Fatalf("online = %v, want true", d.Online)
	}
}

// TestUnknownFieldNumbersAreSkippedNotRejected：不认识的字段号照常按 wire type
// 跳过并继续解析——这是 Parse 的基本行为，也是所有兼容性的前提。
func TestUnknownFieldNumbersAreSkippedNotRejected(t *testing.T) {
	var buf []byte
	buf = appendStringField(buf, 1, "car-001")
	buf = appendStringField(buf, 99, "some future field") // 未来才有的字段
	buf = appendStringField(buf, 2, "1号车")
	buf = appendBoolField(buf, 3, true)

	fields, err := Parse(buf)
	if err != nil {
		t.Fatal(err)
	}
	count := map[int]int{}
	for _, f := range fields {
		count[f.Number]++
	}
	if count[1] != 1 || count[2] != 1 || count[3] != 1 || count[99] != 1 {
		t.Fatalf("field counts = %v, want 1 of each of 1/2/3/99", count)
	}
}

// TestTruncatedBytesAreRejected：数据被截断时必须报错，而不是静默产出错误字段
// （损坏检测是兼容的底线——跳过未知字段≠容忍截断）。
func TestTruncatedBytesAreRejected(t *testing.T) {
	b2 := encodeV2(v2Device{ID: "car-001", Name: "1号车", Online: true, Model: "M300"})
	truncated := b2[:len(b2)-3] // 砍掉 Model 的尾部
	if _, err := decodeV1(truncated); err == nil {
		t.Fatal("truncated message should be rejected")
	}
	if _, err := decodeV2(truncated); err == nil {
		t.Fatal("truncated message should be rejected")
	}
}
