// 来源：ph08-testing 阶段项目 —— 带测试的设备管理 HTTP API
// 一句话说明：存储层表驱动测试 + 并发压力测试（-race 验证）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -race -v ./internal/device
//
// 验证状态：已验证（go1.25.6）
package device

import (
	"errors"
	"fmt"
	"sync"
	"testing"
)

func TestMemoryStoreCRUD(t *testing.T) {
	s := NewMemoryStore(Device{ID: "car-001", Status: "online"})

	t.Run("List 按 ID 排序", func(t *testing.T) {
		_ = s.Create(Device{ID: "car-003", Status: "offline"})
		_ = s.Create(Device{ID: "car-002", Status: "online"})
		got := s.List()
		if len(got) != 3 || got[0].ID != "car-001" || got[1].ID != "car-002" || got[2].ID != "car-003" {
			t.Errorf("List() = %v, 期望按 ID 升序", got)
		}
	})

	t.Run("Get 命中与未命中", func(t *testing.T) {
		d, ok := s.Get("car-001")
		if !ok || d.Status != "online" {
			t.Errorf("Get(car-001) = %v, %v", d, ok)
		}
		if _, ok := s.Get("nope"); ok {
			t.Error("Get(nope) 应当未命中")
		}
	})

	t.Run("Create 重复 ID 报 ErrDuplicate", func(t *testing.T) {
		err := s.Create(Device{ID: "car-001", Status: "x"})
		if !errors.Is(err, ErrDuplicate) {
			t.Errorf("err = %v, 期望 ErrDuplicate", err)
		}
	})

	t.Run("Delete 存在与不存在", func(t *testing.T) {
		if !s.Delete("car-003") {
			t.Error("Delete(car-003) 应当成功")
		}
		if s.Delete("car-003") {
			t.Error("重复 Delete 应当返回 false")
		}
	})
}

// TestMemoryStoreConcurrent 并发压力：多 goroutine 同时读写，-race 下必须干净
func TestMemoryStoreConcurrent(t *testing.T) {
	s := NewMemoryStore()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(3)
		go func(i int) {
			defer wg.Done()
			_ = s.Create(Device{ID: fmt.Sprintf("car-%03d", i), Status: "online"})
		}(i)
		go func(i int) {
			defer wg.Done()
			_, _ = s.Get(fmt.Sprintf("car-%03d", i))
		}(i)
		go func() {
			defer wg.Done()
			_ = s.List()
		}()
	}
	wg.Wait()
	if got := len(s.List()); got != 50 {
		t.Errorf("最终设备数 = %d, 期望 50", got)
	}
}
