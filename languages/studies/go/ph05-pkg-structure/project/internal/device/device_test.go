// 来源：project/ —— 标准 Go 项目模板单元测试
// 一句话说明：internal/device 的表格驱动测试：增删改查、状态校验与文件持久化。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd project && go test ./...
// 验证状态：已验证（Go 1.22.2）
package device

import (
	"errors"
	"path/filepath"
	"testing"
)

// newTestStore 建一个指向临时文件的 Store
func newTestStore(t *testing.T) *Store {
	t.Helper()
	s, err := NewStore(filepath.Join(t.TempDir(), "devices.json"))
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	return s
}

func TestAddAndListSorted(t *testing.T) {
	store := newTestStore(t)
	if err := store.Add(Device{ID: "B", Name: "B 设备"}); err != nil {
		t.Fatalf("Add B: %v", err)
	}
	if err := store.Add(Device{ID: "A", Name: "A 设备"}); err != nil {
		t.Fatalf("Add A: %v", err)
	}
	got := store.List()
	if len(got) != 2 || got[0].ID != "A" || got[1].ID != "B" {
		t.Fatalf("List 期望按 ID 排序的 2 条，得到 %+v", got)
	}
}

func TestAddDuplicate(t *testing.T) {
	store := newTestStore(t)
	if err := store.Add(Device{ID: "D01", Name: "x"}); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if err := store.Add(Device{ID: "D01", Name: "y"}); err == nil {
		t.Fatal("重复 ID 应返回错误")
	}
	if err := store.Add(Device{ID: "D02", Name: ""}); err == nil {
		t.Fatal("空名称应返回错误")
	}
}

func TestSetStateValidation(t *testing.T) {
	store := newTestStore(t)
	if err := store.Add(Device{ID: "D01", Name: "x"}); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if err := store.SetState("D01", "online"); err != nil {
		t.Fatalf("SetState online: %v", err)
	}
	if err := store.SetState("D01", "bogus"); err == nil {
		t.Fatal("非法状态应被拒绝")
	}
	if err := store.SetState("MISSING", "online"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("期望 ErrNotFound，得到 %v", err)
	}
}

func TestDeleteNotFound(t *testing.T) {
	store := newTestStore(t)
	if err := store.Add(Device{ID: "D01", Name: "x"}); err != nil {
		t.Fatalf("Add: %v", err)
	}
	if err := store.Delete("D01"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if err := store.Delete("D01"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("重复删除期望 ErrNotFound，得到 %v", err)
	}
}

func TestPersistReload(t *testing.T) {
	path := filepath.Join(t.TempDir(), "devices.json")
	store, err := NewStore(path)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	if err := store.Add(Device{ID: "D01", Name: "x", State: "fault"}); err != nil {
		t.Fatalf("Add: %v", err)
	}
	// 重开 Store：数据与状态应完整恢复
	reopened, err := NewStore(path)
	if err != nil {
		t.Fatalf("重开 NewStore: %v", err)
	}
	if got := len(reopened.List()); got != 1 {
		t.Fatalf("重开后设备数期望 1，得到 %d", got)
	}
	if got := reopened.List()[0].State; got != "fault" {
		t.Fatalf("重开后状态期望 fault，得到 %q", got)
	}
}
