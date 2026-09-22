// 来源：06-concurrency.md 第 7 章「阶段项目」—— 并发日志处理器
// 一句话说明：日志处理核心：channel 队列接收多来源日志，worker pool 消费，按级别过滤/聚合，超时刷新 + 优雅关闭。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd project && go test ./...
//	cd project && go test -race ./...
//	cd project && go run ./cmd/logd
//
// 验证状态：已验证（Go 1.22.2，go test -race ./... 无 DATA RACE）
package logproc

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"strings"
	"sync"
	"time"
)

// Level 是日志级别，数值越大越严重。
type Level int

const (
	LevelDebug Level = iota
	LevelInfo
	LevelWarn
	LevelError
)

var levelNames = map[Level]string{
	LevelDebug: "DEBUG",
	LevelInfo:  "INFO",
	LevelWarn:  "WARN",
	LevelError: "ERROR",
}

// String 让 Level 可直接用于 %s 格式化。
func (l Level) String() string {
	if name, ok := levelNames[l]; ok {
		return name
	}
	return "UNKNOWN"
}

// ParseLevel 把大小写不敏感的级别字符串解析为 Level，解析失败返回 false。
func ParseLevel(s string) (Level, bool) {
	for l, name := range levelNames {
		if strings.EqualFold(name, s) {
			return l, true
		}
	}
	return 0, false
}

// Entry 是一条待处理日志。Time 由来源方填充。
type Entry struct {
	Time    time.Time
	Level   Level
	Source  string
	Message string
}

// Stats 是一次处理会话的聚合统计（Shutdown 后读取为最终结果）。
type Stats struct {
	Total    int            // 收到的全部条目
	Filtered int            // 被级别过滤丢弃的条目
	ByLevel  map[Level]int  // 各级别输出条数
	BySource map[string]int // 各来源输出条数
}

// Processor 是并发日志处理器。核心是一个有缓冲 channel 队列：多个来源 goroutine
// 并发 Submit，固定数量 worker 消费——"通过通信共享内存"，无需对输入加锁。
type Processor struct {
	minLevel Level
	input    chan Entry
	sink     *bufio.Writer

	statsMu sync.Mutex
	stats   Stats

	sinkMu sync.Mutex // sink 是 bufio.Writer，并发写不安全，用互斥锁串行化

	closeOnce sync.Once
	wg        sync.WaitGroup
}

// New 创建处理器：workers 为消费 worker 数，minLevel 为最低输出级别，
// sink 为输出目的地（bufio 缓冲由 Processor 管理，Shutdown 时刷出）。
func New(workers int, minLevel Level, sink io.Writer) *Processor {
	p := &Processor{
		minLevel: minLevel,
		input:    make(chan Entry, 256),
		sink:     bufio.NewWriter(sink),
		stats: Stats{
			ByLevel:  make(map[Level]int),
			BySource: make(map[string]int),
		},
	}
	p.wg.Add(workers)
	for i := 0; i < workers; i++ {
		go p.worker()
	}
	return p
}

// Submit 提交一条日志，可被多个来源 goroutine 并发调用。
// ctx 取消（如调用方主动停止）时返回 ctx.Err()，调用方应停止继续提交。
// 约定：调用方必须先用 ctx 停止所有 Submit，再调用 Shutdown。
func (p *Processor) Submit(ctx context.Context, e Entry) error {
	select {
	case p.input <- e:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// worker 从输入队列取日志处理，队列关闭且取空后退出。
func (p *Processor) worker() {
	defer p.wg.Done()
	for e := range p.input {
		p.process(e)
	}
}

// process 单条日志的处理流水线：统计 → 级别过滤 → 聚合 → 写输出。
func (p *Processor) process(e Entry) {
	p.statsMu.Lock()
	p.stats.Total++
	if e.Level < p.minLevel {
		p.stats.Filtered++
		p.statsMu.Unlock()
		return
	}
	p.stats.ByLevel[e.Level]++
	p.stats.BySource[e.Source]++
	p.statsMu.Unlock()

	p.sinkMu.Lock()
	fmt.Fprintf(p.sink, "%s [%s] %s: %s\n",
		e.Time.Format("15:04:05.000"), e.Level, e.Source, e.Message)
	p.sinkMu.Unlock()
}

// Flush 把缓冲的输出刷到目的地。可被 FlushLoop 周期性调用（超时刷新）。
func (p *Processor) Flush() {
	p.sinkMu.Lock()
	p.sink.Flush()
	p.sinkMu.Unlock()
}

// FlushLoop 按 interval 周期刷新输出缓冲，ctx 取消时退出。用协程配合 Shutdown 使用。
func (p *Processor) FlushLoop(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			p.Flush()
		}
	}
}

// Shutdown 优雅关闭：关闭输入队列（发送方职责）→ 排空在途日志 → 刷出缓冲 → 等待全部 worker 退出。
// 调用前提：所有来源已停止 Submit（见 Submit 约定）。
func (p *Processor) Shutdown() {
	p.closeOnce.Do(func() {
		close(p.input)
		p.wg.Wait()
		p.Flush()
	})
}

// Stats 返回当前聚合统计的拷贝，可并发调用。
func (p *Processor) Stats() Stats {
	p.statsMu.Lock()
	defer p.statsMu.Unlock()
	byLevel := make(map[Level]int, len(p.stats.ByLevel))
	for l, n := range p.stats.ByLevel {
		byLevel[l] = n
	}
	bySource := make(map[string]int, len(p.stats.BySource))
	for s, n := range p.stats.BySource {
		bySource[s] = n
	}
	return Stats{
		Total:    p.stats.Total,
		Filtered: p.stats.Filtered,
		ByLevel:  byLevel,
		BySource: bySource,
	}
}
