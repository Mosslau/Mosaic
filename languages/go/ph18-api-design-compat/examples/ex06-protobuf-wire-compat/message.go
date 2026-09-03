// 来源：ph18-api-design-compat examples/ex06-protobuf-wire-compat/message.go
// 一句话说明：消息的"模式版本"及其编解码器（主文档 3.8）。把一个 .proto 文件里
// 声明的消息翻译成 Go 结构体 + 手工编码，唯一目的是把"字段号即契约"这一点讲透：
// v1 消息用字段号 1/2/3，v2 追加字段号 4 —— 老 reader（v1 解码器）不认识 4，
// 但因为 wire format 是"按 tag 前进"，它能安全跳过字段 4 并读回它认识的 1/2/3。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

// v1Device 老模式：字段号 1/2/3（一旦发布，编号就属于这些语义，永不复用）。
type v1Device struct {
	ID     string
	Name   string
	Online bool
}

// v2Device 新模式：v1 的三字段 + 追加字段号 4（加字段 = 向前兼容的兼容变更）。
type v2Device struct {
	ID     string
	Name   string
	Online bool
	Model  string // 字段号 4：v2 新增
}

// encodeV1 把 v1 消息编成 wire bytes。
func encodeV1(d v1Device) []byte {
	var buf []byte
	buf = appendStringField(buf, 1, d.ID)
	buf = appendStringField(buf, 2, d.Name)
	buf = appendBoolField(buf, 3, d.Online)
	return buf
}

// encodeV2 把 v2 消息编成 wire bytes（v1 字段号原样保留，只追加字段 4）。
func encodeV2(d v2Device) []byte {
	var buf []byte
	buf = appendStringField(buf, 1, d.ID)
	buf = appendStringField(buf, 2, d.Name)
	buf = appendBoolField(buf, 3, d.Online)
	buf = appendStringField(buf, 4, d.Model)
	return buf
}

// decodeV1 老 reader：只认识字段号 1/2/3。字段 4 出现时照常跳过，
// 其它字段号同样被忽略（proto 编译器生成的 reader 对未知字段也是丢弃或透传）。
func decodeV1(data []byte) (v1Device, error) {
	fields, err := Parse(data)
	if err != nil {
		return v1Device{}, err
	}
	var d v1Device
	for _, f := range fields {
		switch f.Number {
		case 1:
			d.ID = string(f.Bytes)
		case 2:
			d.Name = string(f.Bytes)
		case 3:
			d.Online = f.Varint != 0
			// 字段号 4+：不认识，跳过（这一行为就是向前兼容的实现）
		}
	}
	return d, nil
}

// decodeV2 新 reader：认识 1~4。老服务端发的消息没有字段 4 时，
// Model 落到零值 ""——可选字段缺失用零值，是 proto3 的默认语义。
func decodeV2(data []byte) (v2Device, error) {
	fields, err := Parse(data)
	if err != nil {
		return v2Device{}, err
	}
	var d v2Device
	for _, f := range fields {
		switch f.Number {
		case 1:
			d.ID = string(f.Bytes)
		case 2:
			d.Name = string(f.Bytes)
		case 3:
			d.Online = f.Varint != 0
		case 4:
			d.Model = string(f.Bytes)
		}
	}
	return d, nil
}

func fmtV1(d v1Device) string {
	return fmt.Sprintf("v1Device{ID:%q Name:%q Online:%v}", d.ID, d.Name, d.Online)
}
