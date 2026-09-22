// Package genlog 生成可复现的合成日志行，供 project 的解析基准与 CLI 使用。
// 固定种子（42）保证每次生成的内容一致——基准与验收可以跨机器复现。
package genlog

import (
	"fmt"
	"math/rand"
)

// Line 生成一行 JSON 日志（字段顺序固定，parser.ParseManual 依赖此格式）：
//
//	{"ts":"2026-09-01T10:00:00.123Z","level":"info","device_id":"car-0001","msg":"request ok","latency_ms":12}
//
// level 分布：~70% info / ~20% warn / ~10% error；error 行 latency 更高（模拟真实慢请求）
func Line(r *rand.Rand) string {
	level := "info"
	switch r.Intn(10) {
	case 0, 1:
		level = "warn"
	case 2:
		level = "error"
	}
	latency := r.Intn(300)
	if level == "error" {
		latency = 500 + r.Intn(1500)
	}
	msg := map[string]string{"info": "request ok", "warn": "slow query", "error": "request failed"}[level]
	return fmt.Sprintf(`{"ts":"2026-09-01T10:00:00.%03dZ","level":"%s","device_id":"car-%04d","msg":"%s","latency_ms":%d}`,
		r.Intn(1000), level, r.Intn(100), msg, latency)
}

// Generate 生成 n 行日志（固定种子，可复现）
func Generate(n int) []string {
	r := rand.New(rand.NewSource(42))
	lines := make([]string, n)
	for i := range lines {
		lines[i] = Line(r)
	}
	return lines
}
