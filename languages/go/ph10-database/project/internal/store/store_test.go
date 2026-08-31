package store

import (
	"errors"
	"path/filepath"
	"testing"
	"time"
)

// newTestStore 用 t.TempDir 的临时库
func newTestStore(t *testing.T) *sqliteStore {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "traj.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func TestUpsertDeviceIdempotent(t *testing.T) {
	s := newTestStore(t)
	if err := s.UpsertDevice("car-001"); err != nil {
		t.Fatal(err)
	}
	if err := s.UpsertDevice("car-001"); err != nil { // 二次注册幂等
		t.Fatalf("重复注册应幂等: %v", err)
	}
}

func TestBatchInsertAndLatest(t *testing.T) {
	s := newTestStore(t)
	base := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	points := []Point{
		{DeviceID: "car-001", Lat: 31.1, Lng: 121.2, Speed: 60, TS: base},
		{DeviceID: "car-001", Lat: 31.2, Lng: 121.3, Speed: 70, TS: base.Add(time.Minute)},
	}
	if err := s.BatchInsert(points); err != nil {
		t.Fatalf("BatchInsert: %v", err)
	}
	latest, err := s.Latest("car-001")
	if err != nil {
		t.Fatalf("Latest: %v", err)
	}
	if latest.Speed != 70 || latest.Lat != 31.2 {
		t.Errorf("latest = %+v, want 第二条（70/31.2）", latest)
	}
}

func TestBatchInsertRollbackWholeBatch(t *testing.T) {
	s := newTestStore(t)
	base := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	// 先写入一条合法数据
	if err := s.BatchInsert([]Point{{DeviceID: "car-001", Lat: 31, Lng: 121, Speed: 10, TS: base}}); err != nil {
		t.Fatal(err)
	}
	// 批内第 2 条 device_id 为空 → 整批回滚
	fail := []Point{
		{DeviceID: "car-002", Lat: 32, Lng: 122, Speed: 20, TS: base},
		{DeviceID: "", Lat: 33, Lng: 123, Speed: 30, TS: base},
	}
	if err := s.BatchInsert(fail); err == nil {
		t.Fatal("含空 device_id 的批次应报错")
	}
	// car-002 不应存在（整体回滚）
	if _, err := s.Latest("car-002"); !errors.Is(err, ErrDeviceNotFound) {
		t.Errorf("car-002 应整体回滚: %v", err)
	}
}

func TestLatestMissingDevice(t *testing.T) {
	s := newTestStore(t)
	if _, err := s.Latest("ghost"); !errors.Is(err, ErrDeviceNotFound) {
		t.Errorf("want ErrDeviceNotFound, got %v", err)
	}
}

func TestTrajectoryTimeRange(t *testing.T) {
	s := newTestStore(t)
	base := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	points := []Point{
		{DeviceID: "car-001", Lat: 31.0, Lng: 121.0, Speed: 50, TS: base},                       // 0 分
		{DeviceID: "car-001", Lat: 31.1, Lng: 121.1, Speed: 55, TS: base.Add(5 * time.Minute)},  // 5 分
		{DeviceID: "car-001", Lat: 31.2, Lng: 121.2, Speed: 60, TS: base.Add(10 * time.Minute)}, // 10 分
		{DeviceID: "car-002", Lat: 39.9, Lng: 116.4, Speed: 0, TS: base},                        // 另一台车
	}
	if err := s.BatchInsert(points); err != nil {
		t.Fatal(err)
	}
	// 只取 3~8 分钟区间：应命中 5 分那一条
	got, err := s.Trajectory("car-001", base.Add(3*time.Minute), base.Add(8*time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Speed != 55 {
		t.Errorf("trajectory = %+v, want 只有 55 那一条", got)
	}
	// 全区间升序：3 条，按时间排序
	all, err := s.Trajectory("car-001", base, base.Add(1*time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 3 {
		t.Errorf("len = %d, want 3", len(all))
	}
	for i := 1; i < len(all); i++ {
		if all[i].TS.Before(all[i-1].TS) {
			t.Error("轨迹应按时间升序")
		}
	}
}

// TestBatchInsertConcurrent 并发批量写入：20 goroutine 各写 5 点，全部成功（busy_timeout + WAL）
func TestBatchInsertConcurrent(t *testing.T) {
	s := newTestStore(t)
	base := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	done := make(chan error, 20)
	for w := 0; w < 20; w++ {
		go func(w int) {
			pts := make([]Point, 5)
			for i := range pts {
				pts[i] = Point{DeviceID: "car-x", Lat: float64(w), Lng: float64(i), Speed: 1, TS: base.Add(time.Duration(i) * time.Second)}
			}
			done <- s.BatchInsert(pts)
		}(w)
	}
	for w := 0; w < 20; w++ {
		if err := <-done; err != nil {
			t.Fatalf("并发写入失败: %v", err)
		}
	}
	all, err := s.Trajectory("car-x", base, base.Add(time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 100 {
		t.Errorf("轨迹点数 = %d, want 100（20×5）", len(all))
	}
}
