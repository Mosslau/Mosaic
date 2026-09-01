package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func do(h http.HandlerFunc, id string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/api/devices?id="+id, nil)
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec
}

// 两版 handler 返回同构 JSON（ts 字段随时间变，只比对 device_id/status 与整体可解析性）
func TestBothHandlersSameShape(t *testing.T) {
	for _, tc := range []struct {
		name string
		h    http.HandlerFunc
	}{{"naive", NaiveHandler}, {"fast", FastHandler}} {
		t.Run(tc.name, func(t *testing.T) {
			rec := do(tc.h, "car-001")
			if rec.Code != http.StatusOK {
				t.Fatalf("status=%d", rec.Code)
			}
			var m map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
				t.Fatalf("响应不是合法 JSON: %v", err)
			}
			if m["device_id"] != "car-001" || m["status"] != "online" {
				t.Fatalf("字段不符: %v", m)
			}
			if _, ok := m["ts"].(float64); !ok {
				t.Fatalf("ts 字段缺失或类型错误: %v", m)
			}
		})
	}
}

func TestProfileCPU(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cpu.pprof")
	if err := ProfileCPU(path, NaiveHandler, 300*time.Millisecond); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil || info.Size() == 0 {
		t.Fatalf("CPU profile 未写入: %v", err)
	}
	t.Logf("CPU profile %d 字节，可 go tool pprof -top 分析（README 有实测记录）", info.Size())
}

func TestFastHandlerConcurrent(t *testing.T) {
	done := make(chan struct{})
	for g := 0; g < 8; g++ {
		go func() {
			for {
				select {
				case <-done:
					return
				default:
					rec := do(FastHandler, "car-002")
					if !strings.Contains(rec.Body.String(), "car-002") {
						t.Error("并发响应内容错误")
						return
					}
				}
			}
		}()
	}
	time.Sleep(100 * time.Millisecond)
	close(done)
}

// ---- 基准：直接测热点函数（连同 httptest.NewRecorder 测会被测试桩分配淹没，见文件头） ----

func BenchmarkWriteBodyNaive(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			writeBodyNaive(io.Discard, "car-001", 1756700000)
		}
	})
}

func BenchmarkWriteBodyFast(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			writeBodyFast(io.Discard, "car-001", 1756700000)
		}
	})
}
