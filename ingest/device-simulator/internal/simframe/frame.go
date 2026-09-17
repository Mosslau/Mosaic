// Package simframe 按 GB/T 32960 帧框架(参照)构造二进制测试帧。
//
// 定位: 二进制模拟器(cmd/bin-simulator)的造帧器, 与未来 device-codec 的解码器
// 互为对拍——两边独立实现映射文档《GB32960-二进制协议与字段映射》§5/§5.1/§5.2,
// 对不上即为 bug 或文档歧义。
//
// 字节布局依据: 固有单元(0x01~0x09)按 GB/T 32960-2016 国标布局, 本项目不上报的
// 字段按 §5 无效值约定填 0xFF/0xFFFF; 自定义单元(0x80/0x81)按 §5.2 定稿布局;
// 字节级精度/偏移以国标原文为最终依据。
package simframe

import (
	"encoding/binary"
	"time"
)

// 命令标识(§3)
const (
	CmdLogin    = 0x01 // 车辆登入
	CmdRealtime = 0x02 // 实时信息上报(主力)
	CmdResend   = 0x03 // 补发信息上报
	CmdLogout   = 0x04 // 车辆登出
)

// 应答标志(§3)
const (
	AckCommand = 0x01 // 命令
	AckSuccess = 0x02 // 成功应答
	AckError   = 0x03 // 错误应答
	AckNone    = 0xFE // 无应答(周期实时数据, 减少流量)
)

// 数据加密方式(§2): 第 1 阶段明文, 公网路径开通时切换(设计文档 §8)
const EncPlain = 0x01

// ProtoV1 自定义单元协议版本(§6): 固有单元(0x01~0x09)默认 v1
const ProtoV1 = 0x01

// Frame 按 §2 帧结构打包一帧:
//
//	## (2B) | 命令单元(2B) | VIN(17B 左对齐右补0x00) | 加密方式(1B) | 数据单元长度(2B 大端) | 数据单元 | BCC(1B)
//
// BCC = 从命令单元第 1 字节至数据单元末字节逐字节异或。
func Frame(cmd, ack byte, vin string, dataUnit []byte) []byte {
	f := make([]byte, 0, 24+len(dataUnit)+1)
	f = append(f, '#', '#')
	f = append(f, cmd, ack)

	v := make([]byte, 17) // §8-①: 左对齐右补 0x00
	copy(v, vin)
	f = append(f, v...)

	f = append(f, EncPlain)
	f = binary.BigEndian.AppendUint16(f, uint16(len(dataUnit)))
	f = append(f, dataUnit...)

	var bcc byte
	for _, b := range f[2:] {
		bcc ^= b
	}
	return append(f, bcc)
}

// DataUnit 组装数据单元(§4): 时间(6B, GMT+8 明文, §8-③) + 信息体 × N
func DataUnit(t time.Time, bodies ...[]byte) []byte {
	du := TimeField(t)
	for _, b := range bodies {
		du = append(du, b...)
	}
	return du
}

// TimeField 时间字段: yy MM dd HH mm ss 各 1B, GMT+8(国标口径)
func TimeField(t time.Time) []byte {
	t = t.In(time.FixedZone("GMT+8", 8*3600))
	return []byte{
		byte(t.Year() - 2000),
		byte(t.Month()),
		byte(t.Day()),
		byte(t.Hour()),
		byte(t.Minute()),
		byte(t.Second()),
	}
}
