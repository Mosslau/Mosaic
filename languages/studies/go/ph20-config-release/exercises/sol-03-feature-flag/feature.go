// 来源：ph20-config-release exercises/sol-03-feature-flag/feature.go
// 一句话说明：练习 3 参考实现——灰度开关模块，规则按优先级裁决：
// 紧急关闭（HardOff）> 白名单（内部/灰度组）> 百分比分桶 > 兜底。
// 与 ex03 的区别：这里把"优先级裁决顺序"与"生命周期一致性校验"
// 做进模块里，直接回答"一个用户到底走哪条规则"（主文档 3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"hash/fnv"
)

// Stage 生命周期（与 ex03 对齐，含一致性规则见 Validate）。
type Stage int

const (
	StageIntroduced Stage = iota
	StageBeta
	StageGA
	StageRemoved
)

func (s Stage) String() string {
	switch s {
	case StageIntroduced:
		return "introduced"
	case StageBeta:
		return "beta"
	case StageGA:
		return "ga"
	case StageRemoved:
		return "removed"
	}
	return "unknown"
}

// Feature 是灰度开关规则。字段间有优先级关系（Evaluate 中体现），
// HardOff 用于安全事故时"先关再说"——它优先于一切白名单与放量。
type Feature struct {
	Name     string            // 规则名（也当分桶 salt）
	Stage    Stage             // 生命周期阶段
	HardOff  bool              // 紧急总关：优先级最高，越过白名单与 percent
	Allow    func(string) bool // 白名单判定（nil = 无白名单）
	Percent  int               // 放量百分比（0~100）；负值 = 未配置放量
	Fallback bool              // 身份缺失或规则异常时给的值（默认关）
}

// ErrRemovedMustBeOff 表示 removed 阶段仍开着：生命周期纪律要求摘除期强制关闭，
// 防止"新旧代码都在、却一半开一半关"的混乱。Validate 抓这条。
var ErrRemovedMustBeOff = errors.New("removed-stage feature must be HardOff")

// Validate 校验规则自洽，返回首个不合法项。
// 现在把"规则只能长这样"编译进模块——比散在各调用方好维护。
func (f Feature) Validate() error {
	if f.Stage == StageRemoved && !f.HardOff {
		return fmt.Errorf("feature %q: %w", f.Name, ErrRemovedMustBeOff)
	}
	if f.Percent > 100 || f.Percent < -1 {
		return fmt.Errorf("feature %q: percent=%d 超出 [-1,100]", f.Name, f.Percent)
	}
	return nil
}

// HashBucket 决定性散列（FNV-1a）。同一 (user, feature) 恒定 → 多实例一致。
func HashBucket(user, salt string, total int) int {
	h := fnv.New32a()
	h.Write([]byte(user))
	h.Write([]byte{0})
	h.Write([]byte(salt))
	return int(h.Sum32() % uint32(total))
}

// Evaluate 按优先级裁决规则对该用户是否打开：
//
//  1. HardOff      → false        （紧急止血，越过一切）
//  2. Allow(user)  → true         （白名单：内测/灰度组先进）
//  3. Percent=100  → true
//  4. Percent 中间值 → 分桶 < Percent 命中
//  5. Percent<=0（仅白名单）→ false
//  6. 无用户身份却要分桶 → Fallback（诚实给兜底，不猜）
//
// 放量与白名单叠加（beta 阶段常见：灰度组先行 + 百分比探路）。
func (f Feature) Evaluate(user string) bool {
	if f.HardOff {
		return false // 优先级 1：谁来了都关
	}
	if f.Allow != nil && f.Allow(user) {
		return true // 优先级 2：内部组/灰度名单
	}
	switch {
	case f.Percent >= 100:
		return true // 优先级 3
	case f.Percent <= 0:
		return false // 优先级 5：不放量，等白名单 / 下阶段
	}
	if user == "" {
		return f.Fallback // 优先级 6：要分桶却没有身份
	}
	return HashBucket(user, f.Name, 100) < f.Percent // 优先级 4
}
