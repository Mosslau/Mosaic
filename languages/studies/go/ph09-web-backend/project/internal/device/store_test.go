// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/device 包）
// 一句话说明：存储层测试——List 过滤、Get、Report 更新与并发安全（-race）、ValidSecret。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./internal/device
//	go test -race ./internal/device
//	go test -cover ./internal/device
//
// 验证状态：已验证（go1.25.6）
package device

import (
	"sync"
	"testing"
)

// testDevice 构造种子设备
func testDevice(id, status, secret string) Device {
	return Device{ID: id, Status: status, Secret: secret}
}

func newTestStore() Store {
	return NewMemoryStore(
		testDevice("car-001", "online", "sec-1"),
		testDevice("car-002", "offline", "sec-2"),
	)
}

func TestListFilter(t *testing.T) {
	s := newTestStore()
	if got := len(s.List("")); got != 2 {
		t.Errorf("全部数量 = %d, 期望 2", got)
	}
	if got := len(s.List("online")); got != 1 {
		t.Errorf("online 数量 = %d, 期望 1", got)
	}
	if got := len(s.List("offline")); got != 1 {
		t.Errorf("offline 数量 = %d, 期望 1", got)
	}
}

func TestGet(t *testing.T) {
	s := newTestStore()
	v, ok := s.Get("car-001")
	if !ok || v.Status != "online" {
		t.Errorf("Get(car-001) = %+v, %v", v, ok)
	}
	if _, ok := s.Get("nope"); ok {
		t.Error("Get(nope) 竟然存在")
	}
}

func TestReport(t *testing.T) {
	s := newTestStore()
	v, err := s.Report("car-002", 88.5, 31.2, 121.5)
	if err != nil {
		t.Fatalf("Report 失败: %v", err)
	}
	if v.Speed != 88.5 || v.Lat != 31.2 || v.Lng != 121.5 || v.Status != "online" {
		t.Errorf("上报后设备 = %+v", v)
	}
	if v.UpdatedAt.IsZero() {
		t.Error("UpdatedAt 未更新")
	}
	if _, err := s.Report("nope", 1, 1, 1); err != ErrNotFound {
		t.Errorf("上报不存在设备错误 = %v, 期望 ErrNotFound", err)
	}
}

// TestReportConcurrent 并发上报不丢数据、无数据竞争（配合 -race 验证）
func TestReportConcurrent(t *testing.T) {
	s := newTestStore()
	const n = 50
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			if _, err := s.Report("car-001", 60, 30, 120); err != nil {
				t.Errorf("并发上报失败: %v", err)
			}
		}()
	}
	wg.Wait()
	if v, _ := s.Get("car-001"); v.Speed != 60 {
		t.Errorf("最终速度 = %v, 期望 60", v.Speed)
	}
}

func TestValidSecret(t *testing.T) {
	s := newTestStore()
	if !s.ValidSecret("car-001", "sec-1") {
		t.Error("正确密钥应通过")
	}
	if s.ValidSecret("car-001", "wrong") {
		t.Error("错误密钥不应通过")
	}
	if s.ValidSecret("nope", "sec-1") {
		t.Error("不存在设备不应通过")
	}
}
