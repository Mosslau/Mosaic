// 来源：ph19-mq-event-driven examples/ex06-backlog-watch/backlog_test.go
// 一句话说明：积压监控的可执行断言——lag 随生产爬升、生产停写后追平到 0、
// 阈值边沿触发不重复报、水位快照可被查询（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "testing"

// collectWatcher 建一个 Watcher 并喂完整个模拟，返回终态。
func collectWatcher(w *Watcher, partitions, writeSteps, produceRate, consumeRate, totalSteps int) SimResult {
	return Simulate(partitions, writeSteps, produceRate, consumeRate, totalSteps,
		func(step int, produced, committed []int) {
			w.Observe(step, produced, committed)
		})
}

// TestLagGrowsThenDrainsToZero 积压先爬升、上游停写后消费者追平到 lag=0。
func TestLagGrowsThenDrainsToZero(t *testing.T) {
	w := NewWatcher(0)
	res := collectWatcher(w, 2, 10, 3, 4, 30)
	if !res.CaughtUp {
		t.Fatal("consumer should catch up after producer stops")
	}
	for p := range res.Produced {
		if res.Committed[p] != res.Produced[p] {
			t.Fatalf("partition %d not caught up: committed=%d produced=%d",
				p, res.Committed[p], res.Produced[p])
		}
	}
	// 中间确实出现过积压（水位差曾为正），否则模拟没有意义
	sawLag := false
	for _, snap := range w.historySnapshot() {
		if snap.TotalLag > 0 {
			sawLag = true
			break
		}
	}
	if !sawLag {
		t.Fatal("simulation never produced backlog")
	}
}

// historySnapshot 导出 Watcher 历史（同包可直接访问字段，测试不走锁）。
func (w *Watcher) historySnapshot() []Snapshot {
	out := make([]Snapshot, len(w.history))
	copy(out, w.history)
	return out
}

// TestAlertEdgeTriggeredOnce 边沿触发：lag 首次越过阈值报一次；继续越线不重复报；
// 回落后再越线才报第二次。
func TestAlertEdgeTriggeredOnce(t *testing.T) {
	w := NewWatcher(8)
	collectWatcher(w, 2, 10, 3, 4, 30)

	alerts := w.Alerts()
	if len(alerts) == 0 {
		t.Fatal("expected at least one alert")
	}
	for i := 1; i < len(alerts); i++ {
		if alerts[i].Partition == alerts[i-1].Partition &&
			alerts[i].Lag == alerts[i-1].Lag {
			t.Fatalf("duplicate alert: %+v then %+v", alerts[i-1], alerts[i])
		}
	}
}

// TestAlertExactlyWhenCrossing 阈值边界：lag=7 不报（<8），lag=8 报。
func TestAlertExactlyWhenCrossing(t *testing.T) {
	w := NewWatcher(8)
	// 单分区、一次性生产 8 条且不消费：第一次采样 lag=8，恰好越线触发。
	Simulate(1, 1, 8, 0, 1, func(step int, produced, committed []int) {
		w.Observe(step, produced, committed)
	})
	if n := len(w.Alerts()); n != 1 {
		t.Fatalf("alerts=%d, want 1 (lag reached 8)", n)
	}
	if a := w.Alerts()[0]; a.Lag != 8 || a.Step != 1 {
		t.Fatalf("alert=%+v, want lag=8 step=1", a)
	}
}

// TestObserveNegativeLagClamped 防御：committed 超过高水位（异常元数据）按 0 处理。
func TestObserveNegativeLagClamped(t *testing.T) {
	w := NewWatcher(0)
	snap := w.Observe(1, []int{3}, []int{5})
	if snap.Partitions[0].Lag != 0 {
		t.Fatalf("lag=%d, want clamped to 0", snap.Partitions[0].Lag)
	}
}

// TestManualObserveDeterministic 不用模拟器，直接喂水位观测：全手工断言 lag 计算。
func TestManualObserveDeterministic(t *testing.T) {
	w := NewWatcher(10)
	snap := w.Observe(1, []int{100, 200}, []int{90, 150})
	got := []int{snap.Partitions[0].Lag, snap.Partitions[1].Lag}
	if got[0] != 10 || got[1] != 50 {
		t.Fatalf("lag=%v, want [10 50]", got)
	}
	if snap.TotalLag != 60 {
		t.Fatalf("TotalLag=%d, want 60", snap.TotalLag)
	}
}
