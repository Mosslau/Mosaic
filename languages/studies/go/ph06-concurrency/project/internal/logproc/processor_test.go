// 来源：06-concurrency.md 第 7 章「阶段项目」—— 并发日志处理器（自测）
// 一句话说明：对日志处理核心做单元测试：级别过滤、在途排空、并发提交三组用例。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd project && go test ./...
//	cd project && go test -race ./...
//
// 验证状态：已验证（Go 1.22.2，go test -race ./... 无 DATA RACE）
package logproc

import (
	"bytes"
	"context"
	"strings"
	"sync"
	"testing"
	"time"
)

// entry 构造一条测试日志。
func entry(level Level, source, msg string) Entry {
	return Entry{Time: time.Now(), Level: level, Source: source, Message: msg}
}

// TestLevelFilter 验证级别过滤：低于 minLevel 的条目被丢弃并计入 Filtered。
func TestLevelFilter(t *testing.T) {
	var buf bytes.Buffer
	p := New(2, LevelInfo, &buf)
	ctx := context.Background()

	if err := p.Submit(ctx, entry(LevelDebug, "s", "debug 应被过滤")); err != nil {
		t.Fatalf("Submit: %v", err)
	}
	if err := p.Submit(ctx, entry(LevelInfo, "s", "info 应输出")); err != nil {
		t.Fatalf("Submit: %v", err)
	}
	if err := p.Submit(ctx, entry(LevelError, "s", "error 应输出")); err != nil {
		t.Fatalf("Submit: %v", err)
	}
	p.Shutdown()

	out := buf.String()
	if strings.Contains(out, "debug 应被过滤") {
		t.Errorf("DEBUG 条目不应输出")
	}
	if !strings.Contains(out, "info 应输出") || !strings.Contains(out, "error 应输出") {
		t.Errorf("INFO/ERROR 条目应输出，got:\n%s", out)
	}

	s := p.Stats()
	if s.Total != 3 || s.Filtered != 1 {
		t.Errorf("Total=%d Filtered=%d，期望 3/1", s.Total, s.Filtered)
	}
	if s.ByLevel[LevelInfo] != 1 || s.ByLevel[LevelError] != 1 {
		t.Errorf("ByLevel 统计错误: %+v", s.ByLevel)
	}
}

// TestShutdownDrainsInFlight 验证优雅关闭会排空在途日志：Shutdown 前已提交的条目全部处理。
func TestShutdownDrainsInFlight(t *testing.T) {
	var buf bytes.Buffer
	p := New(2, LevelDebug, &buf)

	const n = 200
	for i := 0; i < n; i++ {
		if err := p.Submit(context.Background(), entry(LevelInfo, "s", "line")); err != nil {
			t.Fatalf("Submit: %v", err)
		}
	}
	p.Shutdown()

	if s := p.Stats(); s.Total != n {
		t.Errorf("Total=%d，期望 %d", s.Total, n)
	}
	if got := strings.Count(buf.String(), "line"); got != n {
		t.Errorf("输出行数=%d，期望 %d", got, n)
	}
}

// TestConcurrentSubmit 验证多来源并发提交：8 个 goroutine 各提交 100 条，
// 总量超过缓冲容量，worker 消费产生背压，Shutdown 后全部处理完。
func TestConcurrentSubmit(t *testing.T) {
	var buf bytes.Buffer
	p := New(4, LevelDebug, &buf)

	const (
		sources = 8
		per     = 100
	)
	var wg sync.WaitGroup
	for i := 0; i < sources; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < per; j++ {
				if err := p.Submit(context.Background(), entry(LevelInfo, "s", "m")); err != nil {
					t.Errorf("Submit: %v", err)
					return
				}
			}
		}(i)
	}
	wg.Wait()
	p.Shutdown()

	want := sources * per
	if s := p.Stats(); s.Total != want {
		t.Errorf("Total=%d，期望 %d", s.Total, want)
	}
}
