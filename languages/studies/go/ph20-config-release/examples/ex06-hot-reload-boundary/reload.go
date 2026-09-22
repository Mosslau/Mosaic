// 来源：ph20-config-release examples/ex06-hot-reload-boundary/reload.go
// 一句话说明：运行时配置热更新的边界——不是"能不能热更"的技术问题，而是
// "该不该热更"的工程判断；对"该热更"的值，用原子快照指针做到请求级无锁
// 生效（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"sort"
	"strings"
	"sync/atomic"
)

// Scope 是某项配置的更新边界。分类依据不是"技术上能不能改"，而是
// "改了能不能安全生效"：涉及连接/监听/证书的值必须重启，调优与开关可热更。
type Scope int

const (
	ScopeHot         Scope = iota // 可热更：下一次读取即生效，无副作用
	ScopeFeatureFlag              // 需"下发 + 全实例一致"语义（feature flag，见 ex03）
	ScopeRestart                  // 必须重启：连接、监听地址、证书等一次性初始化
)

func (s Scope) String() string {
	switch s {
	case ScopeHot:
		return "hot(可热更)"
	case ScopeFeatureFlag:
		return "feature-flag(下发式热更)"
	case ScopeRestart:
		return "restart(必须重启)"
	}
	return "unknown"
}

// Rule 是分类规则的静态表——把"边界"固化成可审查的代码，而不是散在各自字段的注释里。
// 字段：keyPrefix 匹配配置键前缀；scope 该前缀的边界；why 给人类读的原因。
// 顺序敏感：先精确后宽泛；未知键走最保守的 restart（宁重启不冒险热更）。
type Rule struct {
	keyPrefix string
	scope     Scope
	why       string
}

var rules = []Rule{
	// 调优类：请求路径上每次读的值，热更立即影响后续请求，无需重启。
	{"log.level", ScopeHot, "日志级别每次请求即时生效，无连接副作用"},
	{"log.sampling", ScopeHot, "采样率同理"},
	{"rate.limit.", ScopeHot, "限流阈值是运行态参数，热更用于动态压测/封顶"},
	{"circuit.breaker.", ScopeHot, "熔断阈值需随流量形态在线调整"},
	{"http.timeout.", ScopeHot, "超时配置对新建请求生效"},
	// feature flag / 灰度：要"同一时刻全实例一致"，走下发通道，不是本机文件热更。
	{"feature.", ScopeFeatureFlag, "灰度开关需全局一致（ex03），单独通道下发"},
	// 一次性初始化类：改了必须重启，热更只会造成一半新一半旧的诡异状态。
	{"server.port", ScopeRestart, "监听端口在启动时 bind，运行中改不生效"},
	{"server.addr", ScopeRestart, "监听地址同理"},
	{"db.dsn", ScopeRestart, "连接池按 DSN 建立，DSN 变了必须重建（重启）"},
	{"db.pool", ScopeRestart, "连接池在启动时构造，容量调整属资源规划"},
	{"tls.", ScopeRestart, "证书/私钥在握手初始化时加载"},
	{"secret.", ScopeRestart, "密钥应经 secrets 通道轮换（K8s Secret 重启 Pod），不进文件"},
}

// Classify 返回配置键所属的更新边界与原因。key 用小写点路径，如 log.level、
// feature.darkmode.percent、db.dsn。未知前缀保守返回 restart。
func Classify(key string) (Scope, string) {
	for _, r := range rules {
		if strings.HasPrefix(key, r.keyPrefix) {
			return r.scope, r.why
		}
	}
	return ScopeRestart, "未知配置项：保守按必须重启处理"
}

// Snapshot 是不可变配置快照：热更 = 换新指针，绝不原地改旧对象。
// 因此任何持有旧 *Snapshot 的请求继续用旧值（一致），新请求拿新值——
// 不会有"读到一半新一半旧"的撕裂视图。
type Snapshot struct {
	Version  int    // 版本号：每次发布 +1，供观测与审计
	LogLevel string // 演示字段：log.level（ScopeHot）
	MaxQPS   int    // 演示字段：rate.limit.qps（ScopeHot）
}

// LiveConfig 用 atomic 指针持有当前快照：Get 无锁、Store 原子替换。
// 这是"配置中心 watch → 进程内热更"落地时最常用的最小形态（见 4.4）。
type LiveConfig struct {
	ptr atomic.Pointer[Snapshot]
}

func NewLiveConfig(s *Snapshot) *LiveConfig {
	l := &LiveConfig{}
	l.ptr.Store(s)
	return l
}

// Load 返回当前快照。调用方不应修改它——要改就 Store 一个新快照。
func (l *LiveConfig) Load() *Snapshot { return l.ptr.Load() }

// Store 原子替换当前快照。新快照必须由调用方新建（Version+1、新值），
// 旧快照仍被在途请求安全引用（GC 自会回收）。
func (l *LiveConfig) Store(s *Snapshot) { l.ptr.Store(s) }

// Describe 输出分类表（main 演示用），键按字母序保证输出稳定。
func Describe() string {
	var sb strings.Builder
	keys := make([]string, 0, len(rules))
	for _, r := range rules {
		keys = append(keys, r.keyPrefix)
	}
	sort.Strings(keys)
	for _, k := range keys {
		sc, why := Classify(k)
		fmt.Fprintf(&sb, "   %-22s → %-22s %s\n", k, sc, why)
	}
	return sb.String()
}
