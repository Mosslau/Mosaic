// 来源：ph20-config-release examples/ex03-feature-flag/flag.go
// 一句话说明：feature flag 的最小语义——三种灰度策略（关/全开/按用户百分比）、
// 一致性分桶哈希、生命周期阶段与"决策系统不可用时的安全兜底"（主文档 3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"hash/fnv"
)

// Stage 是 feature 的生命周期阶段。生命周期纪律：新功能从低风险人群起步，
// 逐级放大；GA 稳定后也先强制关闭一段时间再删代码（removed），避免
// "老实例还带着旧判断、代码却被删了"的发布错位。
type Stage int

const (
	StageIntroduced Stage = iota // 内测：只对内部/白名单可见，代码刚合入
	StageBeta                    // 灰度：按百分比分桶放量给真实用户
	StageGA                      // 全量：所有人打开，进入稳定期
	StageRemoved                 // 摘除中：强制关闭，观察 N 个发布周期后删代码
)

func (s Stage) String() string {
	switch s {
	case StageIntroduced:
		return "introduced(内测)"
	case StageBeta:
		return "beta(灰度)"
	case StageGA:
		return "GA(全量)"
	case StageRemoved:
		return "removed(摘除中)"
	}
	return "unknown"
}

// StrategyKind 是灰度策略的三形态。feature flag 不是"布尔开关"一个东西：
// 从 0→1 的放量过程需要第三种"百分比"形态（见 Decide）。
type StrategyKind int

const (
	StrategyOff     StrategyKind = iota // 强制关闭（新功能默认、回滚开关）
	StrategyOn                          // 强制全开
	StrategyPercent                     // 按用户分桶放量（0~100）
)

// Strategy 表达一个 feature 当前的放量策略。
type Strategy struct {
	Kind    StrategyKind
	Percent int // 仅 Kind==StrategyPercent 有效：0~100
}

func (s Strategy) String() string {
	switch s.Kind {
	case StrategyOff:
		return "off"
	case StrategyOn:
		return "on"
	case StrategyPercent:
		return fmt.Sprintf("percent=%d%%", s.Percent)
	}
	return "unknown"
}

// Feature 是带生命周期的灰度开关。
type Feature struct {
	Name     string
	Strategy Strategy
	Fallback bool // 决策系统故障/规则缺失时的安全兜底，见 IsEnabled 注释
	Stage    Stage
}

// HashBucket 把 (key, salt) 决定性地散到 [0, total)。用标准库 FNV-1a：
// 不需要密码学强度，只要求「跨进程、跨版本恒定」——同一用户在任意实例上
// 得到同一桶，灰度判断才一致（多实例灰度一致性的全部前提，见主文档 3.3/4.5）。
// salt 里掺 feature 名：让同一位用户在不同 feature 上的灰度互不相关。
// key 与 salt 之间插入 0 字节，防止 (key, salt) 的拼接边界混叠。
func HashBucket(key, salt string, total int) int {
	h := fnv.New32a()
	h.Write([]byte(key))
	h.Write([]byte{0})
	h.Write([]byte(salt))
	return int(h.Sum32() % uint32(total))
}

// IsEnabled 判断 feature 对某个 userKey 是否打开。
// 三种策略的语义：
//   - Off  → 一律 false（新功能默认关闭；也用作线上紧急下线的开关）
//   - On   → 一律 true
//   - Percent → 该用户的分桶号 < Percent 才算命中（放量 N% = 让前 N% 桶的用户可见）
//
// 命中判断对同一 (userKey, feature) 恒定：灰度放量从 20%→50% 时，只有
// 桶落在 [20,50) 的用户"从不可见变可见"，其余用户不受影响——灰度的可预期性。
func (f Feature) IsEnabled(userKey string) bool {
	s := f.Strategy
	switch s.Kind {
	case StrategyOff:
		return false
	case StrategyOn:
		return true
	case StrategyPercent:
		if s.Percent <= 0 {
			return false
		}
		if s.Percent >= 100 {
			return true
		}
		return HashBucket(userKey, f.Name, 100) < s.Percent
	}
	// 未知策略（配置被写坏/版本不匹配）→ 走 Fallback，而不是 panic 或猜一个。
	return f.Fallback
}

// Decide 是 decider 的无状态纯逻辑（不含任何 I/O），因此：
//   - 可以直接放进单元测试断言（feature_test.go）
//   - 多实例共享同一份策略配置时，天然得到一致的灰度结果
//
// 它等价于真实工程里 flag SDK 内部做的判断，只是剥离了"从哪拿配置"。
func Decide(f Feature, userKey string) bool { return f.IsEnabled(userKey) }
