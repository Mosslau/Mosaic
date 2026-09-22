// 来源：ph19-mq-event-driven project/internal/consumer/consumer.go
// 一句话说明：消费循环（消费链路的核心）——按分区顺序从提交点读到高水位，
// 每条消息走「解码 → 幂等查重 → 处理 → 记账/死信」，最终提交 offset。
// 集成 examples/ex01（分区与提交）、ex02/ex03（幂等与死信分类）、ex06（lag）
// 的语义：积压水位 = 高水位 − 提交位置。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package consumer

import (
	"errors"
	"sync"
	"time"

	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
	"tenetlang/go/ph19-mq-event-driven/project/internal/process"
	"tenetlang/go/ph19-mq-event-driven/project/internal/store"
)

// Log 消费端对数据源的只读需求（接口定义在使用方；fake broker / 真 Kafka 皆可实现）。
type Log interface {
	NumPartitions() int
	HighWater(p int) int
	Slice(p, from int) []model.Message
}

// Processor 每条消息的处理动作（由 process 包实现；测试可换替身）。
type Processor interface {
	Process(model.Message) error
}

// Config 重试策略：次数上限 + 退避 + 等待器（测试注入空实现）。
type Config struct {
	MaxAttempts int
	Backoff     func(int) time.Duration
	Sleep       func(time.Duration)
}

// Report 一轮消费的统计（打印与断言用）。
type Report struct {
	Consumed         int // 读到并检查过的消息数
	Applied          int // 副作用真实生效数（每个唯一 MsgID 至多一次）
	DuplicateSkipped int // 幂等窗口拦下的重复投递
	Retried          int // 内部重试次数（抖动恢复前）
	Poisoned         int // 毒消息进死信（解码失败/未知 schema）
	Exhausted        int // 重试耗尽进死信
	MaxLag           int // 本轮观察到最大积压（高水位 − 提交）
}

// Consumer 幂等 + 重试 + 死信的消费循环（串行跑一轮，状态可查询）。
type Consumer struct {
	log       Log
	dedup     *store.SeenWindow
	proc      Processor
	dlog      *store.DeadLog
	cfg       Config
	committed map[int]int // 组级提交：partition -> 下一条 offset
	mu        sync.Mutex
	maxLag    int
}

// New 构造消费者。dedup 应跨成员共享（真实工程落 Redis/DB，见 ex02 说明）。
func New(l Log, dedup *store.SeenWindow, proc Processor, dlog *store.DeadLog, cfg Config) *Consumer {
	if cfg.MaxAttempts <= 0 {
		cfg.MaxAttempts = 1
	}
	if cfg.Sleep == nil {
		cfg.Sleep = func(time.Duration) {}
	}
	return &Consumer{
		log:       l,
		dedup:     dedup,
		proc:      proc,
		dlog:      dlog,
		cfg:       cfg,
		committed: make(map[int]int),
	}
}

// Committed 分区当前提交位置。
func (c *Consumer) Committed(p int) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.committed[p]
}

// MaxLag 本轮最大积压（观测指标：主文档 3.7）。
func (c *Consumer) MaxLag() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.maxLag
}

// RunOnce 消费一轮直到所有分区追平（离线模拟：上游在启动前已写完数据）。
// 真实部署是常驻循环：拉一批 → 处理 → 提交 → 再拉，语义与本方法一致。
func (c *Consumer) RunOnce() Report {
	var rep Report
	for p := 0; p < c.log.NumPartitions(); p++ {
		c.observeLag(p) // 处理前采样：此刻 lag = 高水位 − 提交位置（可能最大）
		from := c.committed[p]
		for _, m := range c.log.Slice(p, from) {
			rep.Consumed++
			out := c.processOne(m)
			rep.Applied += out.applied
			rep.DuplicateSkipped += out.duplicate
			rep.Retried += out.retried
			rep.Poisoned += out.poison
			rep.Exhausted += out.exhausted
		}
		c.mu.Lock()
		c.committed[p] = c.log.HighWater(p) // 本轮末尾提交到高水位
		c.mu.Unlock()
	}
	rep.MaxLag = c.MaxLag()
	return rep
}

type oneResult struct {
	applied, duplicate, retried, poison, exhausted int
}

// processOne 处理单条消息：解码 → 幂等查重 → 处理（有界重试）→ 记账/死信。
func (c *Consumer) processOne(m model.Message) oneResult {
	res := oneResult{}

	// 1. JSON 解码失败 = 毒消息（decode 分类）：死信，不重试、不记账。
	env, derr := model.Decode(m.Payload)
	if derr != nil {
		c.dead(m, "", "", "decode", 1)
		res.poison = 1
		return res
	}
	// 2. 幂等窗口：同一 MsgID 已生效过 → 重复投递，跳过副作用。
	if c.dedup.Seen(env.MsgID) {
		res.duplicate = 1
		return res
	}
	// 3. 处理（内部有界重试；成功才记账——记账前崩溃的窗口期说明见 examples/ex02）。
	attempts := 0
	for {
		attempts++
		err := c.proc.Process(m)
		switch {
		case err == nil:
			c.dedup.Mark(env.MsgID) // 记账：这个键已真实生效过一次
			res.applied = 1
			return res
		case errors.Is(err, process.ErrSchema):
			c.dead(m, env.MsgID, env.VehicleID, "schema", attempts)
			res.poison = 1
			return res
		case errors.Is(err, process.ErrPoison):
			c.dead(m, env.MsgID, env.VehicleID, "poison", attempts)
			res.poison = 1
			return res
		case attempts >= c.cfg.MaxAttempts:
			c.dead(m, env.MsgID, env.VehicleID, "exhausted", attempts)
			res.exhausted = 1
			return res
		}
		// 可重试：退避后重试（测试通过 Config.Sleep 注入空实现）。
		if c.cfg.Backoff != nil {
			c.cfg.Sleep(c.cfg.Backoff(attempts))
		}
		res.retried++
	}
}

// dead 记一条死信（reason 分类让补偿路径与监控能分流）。
func (c *Consumer) dead(m model.Message, msgID, vehicleID, reason string, attempts int) {
	c.dlog.Add(store.DeadEntry{
		MsgID:     msgID,
		VehicleID: vehicleID,
		Reason:    reason,
		Attempts:  attempts,
	})
}

// observeLag 采样单分区 lag 并更新本轮峰值。
func (c *Consumer) observeLag(p int) {
	lag := c.log.HighWater(p) - c.committed[p]
	if lag < 0 {
		lag = 0
	}
	if lag > c.maxLag {
		c.maxLag = lag
	}
}
