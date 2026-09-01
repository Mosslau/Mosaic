// Package parser 提供三种日志行解析实现，供 cmd/logbench 对比性能：
// ParseNaive（encoding/json → map[string]any，通用但慢）、
// ParseStruct（encoding/json → 具名 struct，编译期字段表）、
// ParseManual（手写字节扫描 + strconv，最快但假设值格式简单）。
//
// 日志行格式（genlog 生成的固定格式）：
//
//	{"ts":"2026-09-01T10:00:00.123Z","level":"info","device_id":"car-0001","msg":"request ok","latency_ms":12}
package parser

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// Record 解析产物：只保留本阶段聚合统计需要的字段（ts/msg 忽略）
type Record struct {
	Level     string
	DeviceID  string
	LatencyMs int
}

// ParseNaive 朴素版：每行解析进 map[string]any —— 每行分配一个 map、
// 每个字段装箱成 interface{}、取值时再 fmt.Sprint/类型断言，三版中最慢
func ParseNaive(lines []string) []Record {
	var out []Record
	for _, line := range lines {
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			continue // 坏行跳过（容错）
		}
		rec := Record{
			Level:    fmt.Sprint(m["level"]),
			DeviceID: fmt.Sprint(m["device_id"]),
		}
		if v, ok := m["latency_ms"].(float64); ok { // JSON 数字进 map 一律是 float64
			rec.LatencyMs = int(v)
		}
		out = append(out, rec)
	}
	return out
}

// ParseStruct 优化版 1：具名 struct —— json 包用编译期字段表匹配 tag，
// 跳过 map 的反射路径，且结果 slice 预分配（一次分配装下全部结果）
func ParseStruct(lines []string) []Record {
	out := make([]Record, 0, len(lines))
	for _, line := range lines {
		var rec struct {
			Level     string `json:"level"`
			DeviceID  string `json:"device_id"`
			LatencyMs int    `json:"latency_ms"`
		}
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			continue
		}
		out = append(out, Record{rec.Level, rec.DeviceID, rec.LatencyMs})
	}
	return out
}

// ParseManual 优化版 2：手写扫描 —— 完全不走 encoding/json，
// 用 strings.Index 定位字段、按固定格式截取字符串/数字。
// 假设（教学性取舍，注释说明）：字段值是简单字符串或整数、不含转义引号——
// 通用性差，换来的是数量级的速度；值格式变化时需同步维护本函数
func ParseManual(lines []string) []Record {
	out := make([]Record, 0, len(lines))
	for _, line := range lines {
		if rec, ok := parseLineManual(line); ok {
			out = append(out, rec)
		}
	}
	return out
}

// parseLineManual 手工提取三个字段；任一字段缺失即视为坏行
func parseLineManual(line string) (Record, bool) {
	var rec Record
	v, ok := fieldString(line, `"level":"`)
	if !ok {
		return rec, false
	}
	rec.Level = v

	v, ok = fieldString(line, `"device_id":"`)
	if !ok {
		return rec, false
	}
	rec.DeviceID = v

	n, ok := fieldInt(line, `"latency_ms":`)
	if !ok {
		return rec, false
	}
	rec.LatencyMs = n
	return rec, true
}

// fieldString 定位 key 后截取到下一个双引号的值（不含引号）
func fieldString(s, key string) (string, bool) {
	i := strings.Index(s, key)
	if i < 0 {
		return "", false
	}
	start := i + len(key)
	end := strings.IndexByte(s[start:], '"')
	if end < 0 {
		return "", false
	}
	return s[start : start+end], true
}

// fieldInt 定位 key 后截取连续数字并转 int
func fieldInt(s, key string) (int, bool) {
	i := strings.Index(s, key)
	if i < 0 {
		return 0, false
	}
	start := i + len(key)
	end := start
	for end < len(s) && s[end] >= '0' && s[end] <= '9' {
		end++
	}
	if end == start {
		return 0, false
	}
	n, err := strconv.Atoi(s[start:end])
	if err != nil {
		return 0, false
	}
	return n, true
}
