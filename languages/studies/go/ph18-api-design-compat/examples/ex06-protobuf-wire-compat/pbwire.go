// 来源：ph18-api-design-compat examples/ex06-protobuf-wire-compat/pbwire.go
// 一句话说明：protobuf wire format 的最小实现（主文档 4 章）。消息编码 = 一串
// (tag, payload)：tag = (字段号 << 3) | wire type。本次只实现三种 wire type：
// 0=varint（int/bool/enum）、2=length-delimited（string/bytes/嵌套消息）、5=32-bit。
// 教学要点：解码器"按 tag 顺序流式前进"，遇到不认识的字段号就跳过 payload——
// 这条"跳过未知字段"规则是 protobuf 加字段仍向前兼容的全部秘密（主文档 3.8/4 章）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .（打印 v1/v2 编码字节与兼容观察）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"fmt"
)

// Wire type 常量（protobuf wire format 定义）。
const (
	wireVarint  = 0 // int/bool/enum/负数按 10 字节
	wireBytes   = 2 // string/bytes/嵌套消息
	wireFixed32 = 5
)

// Field 解码后的一条字段：字段号 + 负载（按 wire type 解释）。
type Field struct {
	Number int
	Wire   int
	Varint uint64
	Bytes  []byte
}

// appendVarint 把 varint 追加到 buf 并返回。varint：每字节 7 位有效数据，
// 最高位是"是否还有下一字节"的延续位。
func appendVarint(buf []byte, v uint64) []byte {
	for v >= 0x80 {
		buf = append(buf, byte(v)|0x80)
		v >>= 7
	}
	return append(buf, byte(v))
}

// appendTag 追加 (字段号<<3 | wire) 的 varint。
func appendTag(buf []byte, number, wire int) []byte {
	return appendVarint(buf, uint64(number)<<3|uint64(wire))
}

// appendStringField 追加一条 length-delimited 字符串字段。
func appendStringField(buf []byte, number int, s string) []byte {
	buf = appendTag(buf, number, wireBytes)
	buf = appendVarint(buf, uint64(len(s)))
	return append(buf, s...)
}

// appendBoolField 追加一条 bool 字段（varint 0/1）。
func appendBoolField(buf []byte, number int, b bool) []byte {
	buf = appendTag(buf, number, wireVarint)
	if b {
		return appendVarint(buf, 1)
	}
	return appendVarint(buf, 0)
}

// skipVarint 从 data[pos:] 读出 varint，返回值与新的位置。
func skipVarint(data []byte, pos int) (uint64, int, error) {
	var v uint64
	for shift := uint(0); shift < 64; shift += 7 {
		if pos >= len(data) {
			return 0, pos, fmt.Errorf("varint truncated at byte %d", pos)
		}
		b := data[pos]
		pos++
		v |= uint64(b&0x7f) << shift
		if b&0x80 == 0 {
			return v, pos, nil
		}
	}
	return 0, pos, fmt.Errorf("varint overflows 64 bits")
}

// Parse 把一条 protobuf 消息解成字段列表。编码器不认识语义，只按 tag 顺序前进：
// 对每一个 tag 读出 wire type，据此跳过/读取负载。不认识的字段号不会被拒绝，
// 而是照常按 wire type 前进——这就是"未知字段被安全忽略"的实现机制。
func Parse(data []byte) ([]Field, error) {
	var out []Field
	pos := 0
	for pos < len(data) {
		tag, next, err := skipVarint(data, pos)
		if err != nil {
			return nil, err
		}
		pos = next
		number := int(tag >> 3)
		wire := int(tag & 7)
		f := Field{Number: number, Wire: wire}
		switch wire {
		case wireVarint:
			v, p, err := skipVarint(data, pos)
			if err != nil {
				return nil, err
			}
			f.Varint = v
			pos = p
		case wireBytes:
			n, p, err := skipVarint(data, pos)
			if err != nil {
				return nil, err
			}
			pos = p
			if n > uint64(len(data)-pos) {
				return nil, fmt.Errorf("field %d length %d overruns message", number, n)
			}
			f.Bytes = data[pos : pos+int(n)]
			pos += int(n)
		case wireFixed32:
			if len(data)-pos < 4 {
				return nil, fmt.Errorf("field %d truncated fixed32", number)
			}
			pos += 4
		default:
			// wire type 3/4（group）与 1/5 在本实现中要么不支持要么已覆盖；
			// 撞到完全不认识的 wire type 说明数据损坏，按 protobuf 惯例报错。
			return nil, fmt.Errorf("field %d unsupported wire type %d", number, wire)
		}
		out = append(out, f)
	}
	return out, nil
}
