// 来源：ph21-data-ingest-gateway examples/ex01-mqtt-minimal/packet.go
// 一句话说明：MQTT 3.1.1 最小报文子集的编解码——CONNECT/CONNACK/PUBLISH(QoS0)/
// SUBSCRIBE/SUBACK/PINGREQ/PINGRESP/DISCONNECT。固定头 1 字节 + 剩余长度变长编码
// + 可变头/负载，是 ex01 自研协议的地基（主文档 3.1/4.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -broker 127.0.0.1:18830   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"
)

// MQTT 报文类型（固定头高 4 位）。
const (
	typeCONNECT    byte = 1
	typeCONNACK    byte = 2
	typePUBLISH    byte = 3
	typeSUBSCRIBE  byte = 8
	typeSUBACK     byte = 9
	typePINGREQ    byte = 12
	typePINGRESP   byte = 13
	typeDISCONNECT byte = 14
)

// ErrNotAuthorized 连接被 broker 拒绝（CONNACK rc=5）。重连逻辑必须区分它
// 与网络错误——鉴权失败重试无意义（主文档 3.2/3.3）。
var ErrNotAuthorized = errors.New("mqtt: connection not authorized")

// encodeRL 把剩余长度编码成 MQTT 变长格式：每字节低 7 位存值、最高位表示续段，
// 最多 4 字节。小负载（典型遥测帧 <128B）只占 1 字节——这是 MQTT 省字节的关键。
func encodeRL(n int) ([]byte, error) {
	if n < 0 || n > 0x0FFFFFFF { // 4 字节变长的上限
		return nil, fmt.Errorf("mqtt: remaining length %d 超上限", n)
	}
	var out []byte
	for {
		b := byte(n % 128)
		n /= 128
		if n > 0 {
			b |= 0x80 // 续段标志
		}
		out = append(out, b)
		if n == 0 {
			return out, nil
		}
	}
}

// decodeRL 从字节流解码变长剩余长度，返回 (值, 消耗字节数)。
func decodeRL(b []byte) (int, int, error) {
	mult, val := 1, 0
	for i := 0; i < len(b); i++ {
		val += int(b[i]&0x7F) * mult
		if b[i]&0x80 == 0 {
			return val, i + 1, nil
		}
		mult *= 128
	}
	return 0, 0, errors.New("mqtt: 剩余长度编码不完整")
}

// writeStr 写 MQTT UTF-8 字符串：2 字节大端长度 + 内容。
func writeStr(buf []byte, s string) []byte {
	if len(s) > 0xFFFF {
		panic("mqtt: 字符串超长") // 编码侧只可能来自内部 bug
	}
	buf = binary.BigEndian.AppendUint16(buf, uint16(len(s)))
	return append(buf, s...)
}

// connectPacket CONNECT 报文：协议名 MQTT/level 4 + 连接标志 + keepalive + clientID/user/password。
// 只支持 clean session + username + password（QoS0 子集不需要遗嘱/保留）。
type connectPacket struct {
	ClientID  string
	Username  string
	Password  string
	KeepAlive uint16 // 秒；0 表示不要求保活
}

func (p connectPacket) encode() []byte {
	buf := make([]byte, 0, 64)
	buf = append(buf, 0x00, 0x04, 'M', 'Q', 'T', 'T') // 协议名
	buf = append(buf, 4)                              // 协议级别 3.1.1
	flags := byte(0x02)                               // clean session
	if p.Username != "" {
		flags |= 0x80
	}
	if p.Password != "" {
		flags |= 0x40
	}
	buf = append(buf, flags)
	buf = binary.BigEndian.AppendUint16(buf, p.KeepAlive)
	buf = writeStr(buf, p.ClientID)
	if p.Username != "" {
		buf = writeStr(buf, p.Username)
	}
	if p.Password != "" {
		buf = writeStr(buf, p.Password)
	}
	return frame(typeCONNECT, 0, buf)
}

// decodeConnect 从固定头后的剩余部分解析 CONNECT（要求用户名/密码存在）。
func decodeConnect(rest []byte) (connectPacket, error) {
	var p connectPacket
	if len(rest) < 10 || string(rest[2:6]) != "MQTT" {
		return p, errors.New("mqtt: CONNECT 协议名缺失或非法")
	}
	if rest[6] != 4 {
		return p, fmt.Errorf("mqtt: 不支持的协议级别 %d", rest[6])
	}
	flags := rest[7]
	p.KeepAlive = binary.BigEndian.Uint16(rest[8:10])
	body := rest[10:]
	s, err := takeStr(body)
	if err != nil {
		return p, err
	}
	p.ClientID = s
	body = body[2+len(s):]
	if flags&0x80 != 0 { // username
		s, err = takeStr(body)
		if err != nil {
			return p, err
		}
		p.Username = s
		body = body[2+len(s):]
	}
	if flags&0x40 != 0 { // password
		s, err = takeStr(body)
		if err != nil {
			return p, err
		}
		p.Password = s
	}
	return p, nil
}

// connackPacket CONNACK：session present(0) + 返回码（0 成功 / 5 未授权）。
func connackPacket(rc byte) []byte {
	return frame(typeCONNACK, 0, []byte{0, rc})
}

// publishPacket QoS0 PUBLISH：topic + payload（无包 ID）。
type publishPacket struct {
	Topic   string
	Payload []byte
}

func (p publishPacket) encode() []byte {
	buf := writeStr(nil, p.Topic)
	buf = append(buf, p.Payload...)
	return frame(typePUBLISH, 0, buf) // QoS0：标志位全 0
}

func decodePublish(rest []byte) (publishPacket, error) {
	var p publishPacket
	s, err := takeStr(rest)
	if err != nil {
		return p, err
	}
	p.Topic = s
	p.Payload = append([]byte(nil), rest[2+len(s):]...)
	return p, nil
}

// subscribePacket SUBSCRIBE：包 ID + (filter, qos) 对。ex01 每订阅一包一个 filter。
type subscribePacket struct {
	PacketID uint16
	Filter   string
}

func (p subscribePacket) encode() []byte {
	buf := binary.BigEndian.AppendUint16(nil, p.PacketID)
	buf = writeStr(buf, p.Filter)
	buf = append(buf, 0) // requested QoS 0
	return frame(typeSUBSCRIBE, 2, buf)
}

func decodeSubscribe(rest []byte) (subscribePacket, error) {
	var p subscribePacket
	if len(rest) < 2 {
		return p, errors.New("mqtt: SUBSCRIBE 无包 ID")
	}
	p.PacketID = binary.BigEndian.Uint16(rest[:2])
	body := rest[2:]
	s, err := takeStr(body)
	if err != nil {
		return p, err
	}
	p.Filter = s
	return p, nil
}

func subackPacket(packetID uint16, grantedQoS byte) []byte {
	buf := binary.BigEndian.AppendUint16(nil, packetID)
	buf = append(buf, grantedQoS)
	return frame(typeSUBACK, 0, buf)
}

// frame 组完整报文：固定头（类型 + 标志）+ 变长剩余长度 + 剩余部分。
func frame(typ, flags byte, rest []byte) []byte {
	rl, err := encodeRL(len(rest))
	if err != nil {
		panic(err) // 编码侧输入都是受控的小报文
	}
	out := []byte{typ<<4 | flags}
	out = append(out, rl...)
	return append(out, rest...)
}

// takeStr 从 b 头部取一段 MQTT UTF-8 字符串。
func takeStr(b []byte) (string, error) {
	if len(b) < 2 {
		return "", errors.New("mqtt: 字符串长度头缺失")
	}
	n := int(binary.BigEndian.Uint16(b[:2]))
	if len(b) < 2+n {
		return "", errors.New("mqtt: 字符串截断")
	}
	return string(b[2 : 2+n]), nil
}

// readFrame 从连接读一整个报文：先读固定头（1 字节类型 + 变长剩余长度），
// 再按剩余长度读满负载。length-prefix 语义与主文档 3.5 的 readFrame 同构。
func readFrame(r io.Reader) (typ byte, rest []byte, err error) {
	var hdr [1]byte
	if _, err = io.ReadFull(r, hdr[:]); err != nil {
		return 0, nil, err
	}
	typ = hdr[0] >> 4
	// 剩余长度最多 4 字节，逐字节读直到续段标志清除。
	mult, rl := 1, 0
	for i := 0; i < 4; i++ {
		var b [1]byte
		if _, err = io.ReadFull(r, b[:]); err != nil {
			return 0, nil, err
		}
		rl += int(b[0]&0x7F) * mult
		if b[0]&0x80 == 0 {
			break
		}
		mult *= 128
	}
	if rl < 0 || rl > 1<<24 {
		return 0, nil, fmt.Errorf("mqtt: 非法剩余长度 %d", rl)
	}
	rest = make([]byte, rl)
	if _, err = io.ReadFull(r, rest); err != nil {
		return 0, nil, err
	}
	return typ, rest, nil
}
