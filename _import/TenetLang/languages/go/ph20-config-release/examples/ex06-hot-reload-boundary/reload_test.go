// 来源：ph20-config-release examples/ex06-hot-reload-boundary/reload_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./... && go test -race ./...    验证状态：已验证
//
//	（go1.25.6 本机实测 vet/build/test 及 -race 全绿，gofmt 合规）
package main

import (
	"sync"
	"testing"
)

func TestClassifyBoundaries(t *testing.T) {
	cases := []struct {
		key  string
		want Scope
	}{
		{"log.level", ScopeHot},
		{"log.sampling", ScopeHot},
		{"rate.limit.qps", ScopeHot},
		{"circuit.breaker.error_rate", ScopeHot},
		{"http.timeout.read", ScopeHot},
		{"feature.darkmode.percent", ScopeFeatureFlag},
		{"feature.realtime-map", ScopeFeatureFlag},
		{"server.port", ScopeRestart},
		{"server.addr", ScopeRestart},
		{"db.dsn", ScopeRestart},
		{"db.pool.max_open", ScopeRestart},
		{"tls.cert_path", ScopeRestart},
		{"secret.api_key", ScopeRestart},
	}
	for _, c := range cases {
		got, _ := Classify(c.key)
		if got != c.want {
			t.Errorf("Classify(%q) = %v, want %v", c.key, got, c.want)
		}
	}
}

func TestClassifyUnknownKeyIsConservative(t *testing.T) {
	// 新加的配置项没在规则表里：宁重启不冒险热更。
	got, why := Classify("billing.currency")
	if got != ScopeRestart {
		t.Errorf("未知键分类 = %v, want restart（保守默认）", got)
	}
	if why == "" {
		t.Error("未知键应给出人类可读原因")
	}
}

func TestLiveConfigSwapIsAtomic(t *testing.T) {
	lc := NewLiveConfig(&Snapshot{Version: 1, LogLevel: "INFO", MaxQPS: 100})
	if got := lc.Load().LogLevel; got != "INFO" {
		t.Fatalf("初始 LogLevel = %q, want INFO", got)
	}
	lc.Store(&Snapshot{Version: 2, LogLevel: "DEBUG", MaxQPS: 500})
	s := lc.Load()
	if s.Version != 2 || s.LogLevel != "DEBUG" || s.MaxQPS != 500 {
		t.Errorf("热更后快照 = %+v, want version2/DEBUG/500", s)
	}
}

func TestHoldersOfOldSnapshotStayConsistent(t *testing.T) {
	// 热更语义的关键：在途请求持有旧指针，不受后续 Store 影响——
	// 旧请求继续用旧值，新请求用新值，不会出现撕裂视图。
	lc := NewLiveConfig(&Snapshot{Version: 1, LogLevel: "INFO"})
	old := lc.Load() // 模拟"已经读到一半"的请求持有的引用
	lc.Store(&Snapshot{Version: 2, LogLevel: "DEBUG"})
	if old.LogLevel != "INFO" || old.Version != 1 {
		t.Errorf("旧引用被热更污染：%+v", old)
	}
	if lc.Load().LogLevel != "DEBUG" {
		t.Error("Store 后 Load 应返回新值")
	}
}

func TestConcurrentReadersNeverSeeTornView(t *testing.T) {
	// -race 下并发读 + 交替热更：任何一次 Load 都必须读到"完整成对"的快照
	// （version 与 logLevel 一一对应），不许出现 v1 配 DEBUG / v2 配 INFO。
	lc := NewLiveConfig(&Snapshot{Version: 1, LogLevel: "INFO"})

	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 5000; j++ {
				s := lc.Load()
				if !(s.Version == 1 && s.LogLevel == "INFO" ||
					s.Version == 2 && s.LogLevel == "DEBUG") {
					t.Errorf("读到撕裂快照：version=%d logLevel=%s", s.Version, s.LogLevel)
					return
				}
			}
		}()
	}
	for j := 0; j < 500; j++ {
		lc.Store(&Snapshot{Version: 1, LogLevel: "INFO"})
		lc.Store(&Snapshot{Version: 2, LogLevel: "DEBUG"})
	}
	wg.Wait()
}
