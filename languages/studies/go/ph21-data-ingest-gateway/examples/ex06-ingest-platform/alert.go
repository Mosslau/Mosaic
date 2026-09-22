// 来源：ph21-data-ingest-gateway examples/ex06-metrics-platform/alert.go
// 一句话说明：规则即数据的告警引擎——每条规则是阈值/比较/等级/静默期，Evaluate
// 对最新值裁决；规则声明式（ph03 结构 + ph18 契约思想），便于审查与回放。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import "time"

// Rule 一条告警规则（数据而非代码分支）。
type Rule struct {
	ID        string
	Metric    string // 如 value
	Threshold float64
	Above     bool   // true: > threshold；false: < threshold
	Severity  string // info/warn/critical
}

// Alert 命中后产生的一条告警。
type Alert struct {
	Source   string
	RuleID   string
	Severity string
	Value    float64
	Ts       time.Time
}

// AlertEngine 规则集 + 静默期（同一个数据源同一规则在冷却期内不重复告警）。
type AlertEngine struct {
	rules    []Rule
	cooldown time.Duration
	last     map[string]time.Time // source|ruleID → 上次告警时间
}

// NewAlertEngine 建引擎并注册两条默认规则（CPU 高水位 80% 与磁盘过热 75℃）。
func NewAlertEngine() *AlertEngine {
	return &AlertEngine{
		rules: []Rule{
			{ID: "value-warn", Metric: "value", Threshold: 80, Above: true, Severity: "warn"},
			{ID: "value-critical", Metric: "value", Threshold: 90, Above: true, Severity: "critical"},
		},
		cooldown: 10 * time.Second,
		last:     map[string]time.Time{},
	}
}

// Evaluate 对 (source, metric) 的当前值裁决，返回命中且未在冷却期的告警。
func (a *AlertEngine) Evaluate(source, metric string, value float64, now time.Time) []Alert {
	var out []Alert
	for _, r := range a.rules {
		if r.Metric != metric {
			continue
		}
		hit := (r.Above && value > r.Threshold) || (!r.Above && value < r.Threshold)
		if !hit {
			continue
		}
		key := source + "|" + r.ID
		if lt, ok := a.last[key]; ok && now.Sub(lt) < a.cooldown {
			continue // 冷却期：同一规则不刷屏
		}
		a.last[key] = now
		out = append(out, Alert{Source: source, RuleID: r.ID, Severity: r.Severity, Value: value, Ts: now})
	}
	return out
}
