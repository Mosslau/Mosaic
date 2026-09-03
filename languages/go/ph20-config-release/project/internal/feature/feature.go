// Package feature 提供灰度开关裁决：紧急关闭 > 白名单 > 百分比分桶 > 兜底，
// 全部是确定性纯函数（同一 user+feature 恒定），多实例共享规则即得一致结果。
package feature

import (
	"errors"
	"fmt"
	"hash/fnv"
)

// Feature 是灰度规则。HardOff 优先级最高，用于安全事故先止血。
type Feature struct {
	Name     string            // 规则名（也作分桶 salt）
	HardOff  bool              // 紧急关闭：越过一切
	Allow    func(string) bool // 白名单（nil = 无）
	Percent  int               // 放量百分比 0~100；负值 = 未配置放量
	Fallback bool              // 空身份/异常时的兜底
}

// ErrInvalidPercent 表示放量百分比超出 [0,100]。
var ErrInvalidPercent = errors.New("invalid percent")

// Validate 校验规则自洽（构建期不炸，决策前拦）。
func (f Feature) Validate() error {
	if f.Percent < 0 || f.Percent > 100 {
		return fmt.Errorf("feature %q: %w: %d", f.Name, ErrInvalidPercent, f.Percent)
	}
	return nil
}

// HashBucket 决定性散列（FNV-1a）：同 (user, salt) → 同桶，跨进程恒定。
func HashBucket(user, salt string, total int) int {
	h := fnv.New32a()
	h.Write([]byte(user))
	h.Write([]byte{0})
	h.Write([]byte(salt))
	return int(h.Sum32() % uint32(total))
}

// Evaluate 按优先级裁决 feature 对 user 是否打开（见包注释顺序）。
func Evaluate(f Feature, user string) bool {
	if f.HardOff {
		return false
	}
	if f.Allow != nil && f.Allow(user) {
		return true
	}
	switch {
	case f.Percent >= 100:
		return true
	case f.Percent <= 0:
		return false
	}
	if user == "" {
		return f.Fallback
	}
	return HashBucket(user, f.Name, 100) < f.Percent
}
