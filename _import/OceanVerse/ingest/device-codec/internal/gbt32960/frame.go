// Package gbt32960 GB/T 32960 二进制帧编解码器(参照国标, 映射文档 v1.4 定稿)。
//
// 职责: L1 线协议 → L2 标准契约(vehicle.VehicleReport) 的上行解析。
// 与网关 internal/simframe 造帧器互为对拍(两边独立实现同一规格)。
//
// 版本纪律(§7): 未知协议版本不猜、直接 DLQ; 新协议版本 = 新增解码器, 不改存量。
// 无效值约定(§5): 0xFF/0xFFFF 等无效值在解码时丢弃(字段不设置)。
package gbt32960

import (
	"encoding/binary"
	"errors"
	"fmt"
	"time"
)

// 帧级错误(整帧进 DLQ 的原因)
var (
	ErrTooShort = errors.New("帧长度不足")
	ErrSync     = errors.New("帧同步失败: 起始符不是 ##")
	ErrLength   = errors.New("数据单元长度与实际不符")
	ErrBCC      = errors.New("BCC 校验失败")
	ErrNoTime   = errors.New("数据单元不含完整时间字段(6B)")
	ErrBadTime  = errors.New("时间字段越界")
)

// Frame 包头轻解析结果(§2 帧结构)
type Frame struct {
	Cmd  byte   // 命令标识
	Ack  byte   // 应答标志
	VIN  string // 去 0x00 填充(§8-①)
	Enc  byte   // 数据加密方式
	Data []byte // 数据单元(时间 6B + 信息体×N)
}

// ParseFrame 帧同步 + 包头解析 + BCC 校验。出错即整帧不可信, 调用方进 DLQ。
func ParseFrame(raw []byte) (*Frame, error) {
	if len(raw) < 26 { // 2+2+17+1+2 + 至少 1B 数据 + 1B 校验
		return nil, fmt.Errorf("%w: %d", ErrTooShort, len(raw))
	}
	if raw[0] != '#' || raw[1] != '#' {
		return nil, ErrSync
	}
	dlen := int(binary.BigEndian.Uint16(raw[22:24]))
	if len(raw) != 24+dlen+1 {
		return nil, fmt.Errorf("%w: 声明 %d, 实际 %d", ErrLength, dlen, len(raw)-25)
	}
	var bcc byte
	for _, b := range raw[2 : len(raw)-1] {
		bcc ^= b
	}
	if bcc != raw[len(raw)-1] {
		return nil, fmt.Errorf("%w", ErrBCC)
	}
	vin := raw[4:21]
	end := len(vin)
	for end > 0 && vin[end-1] == 0 {
		end--
	}
	return &Frame{
		Cmd:  raw[2],
		Ack:  raw[3],
		VIN:  string(vin[:end]),
		Enc:  raw[21],
		Data: raw[24 : 24+dlen],
	}, nil
}

// parseTime 数据单元时间(6B, GMT+8 明文, §8-③) → Unix 秒。
//
// 范围校验(2026-09-20 补): 修复前直接把 6 个字节喂给 time.Date, 而 time.Date 会**归一化**
// 越界字段 —— month=13 变成次年 1 月, day=0 变成上月最后一天, hour=99 变成几天后。
// 于是"字节明显非法"的帧会解出一个看似合法的时间戳, 并且一路通过契约的 ts 容差校验
// (只要落在近 7 天内), 让坏帧被当成好数据。这里用**回读比对**拒绝一切会归一化的输入:
// 让 time.Date 走一遍, 再把年/月/日/时/分/秒读回来与原字节比, 不等即非法。
func parseTime(du []byte) (int64, error) {
	if len(du) < 6 {
		return 0, ErrNoTime
	}
	yy, mm, dd, hh, mi, ss := int(du[0]), int(du[1]), int(du[2]), int(du[3]), int(du[4]), int(du[5])
	t := time.Date(2000+yy, time.Month(mm), dd, hh, mi, ss, 0,
		time.FixedZone("GMT+8", 8*3600))
	// 月/日/时/分/秒都必须原样读回(秒级精度, 无夏令时问题: GMT+8 固定偏移)
	if t.Year() != 2000+yy || int(t.Month()) != mm || t.Day() != dd ||
		t.Hour() != hh || t.Minute() != mi || t.Second() != ss {
		return 0, fmt.Errorf("%w: 时间字段非法 yy=%d MM=%d dd=%d HH=%d mm=%d ss=%d",
			ErrBadTime, yy, mm, dd, hh, mi, ss)
	}
	return t.Unix(), nil
}
