package main

import (
	"database/sql"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := newDB()
	if err != nil {
		t.Fatalf("newDB: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestBatchUpsertAllValid(t *testing.T) {
	db := newTestDB(t)
	items := []DeviceStatus{{"car-001", "online", 88.5}, {"car-002", "online", 60}}
	if err := BatchUpsert(db, items); err != nil {
		t.Fatalf("BatchUpsert: %v", err)
	}
	n, _ := count(db)
	if n != 2 {
		t.Errorf("count = %d, want 2", n)
	}
}

// TestBatchUpsertRollbackWholeBatch 含非法条目：整批回滚，COUNT 不变
func TestBatchUpsertRollbackWholeBatch(t *testing.T) {
	db := newTestDB(t)
	// 先放两条合法数据打底
	if err := BatchUpsert(db, []DeviceStatus{{"car-001", "online", 1}, {"car-002", "online", 2}}); err != nil {
		t.Fatal(err)
	}
	before, _ := count(db)
	// 批次里第 2 条 device_id 为空 → 整批失败
	fail := []DeviceStatus{{"car-003", "online", 3}, {"", "offline", 4}}
	if err := BatchUpsert(db, fail); err == nil {
		t.Fatal("含空 device_id 的批次应返回错误")
	}
	after, _ := count(db)
	if before != after {
		t.Errorf("回滚后 count 变化: before=%d after=%d（应整体回滚）", before, after)
	}
	// car-003 不应存在（第 1 条虽然合法也被回滚）
	var exists int
	db.QueryRow("SELECT COUNT(*) FROM device_status WHERE device_id='car-003'").Scan(&exists)
	if exists != 0 {
		t.Error("car-003 不应写入（整体回滚）")
	}
}

// TestBatchUpsertUpdatesExisting 重复 device_id：upsert 覆盖旧值
func TestBatchUpsertUpdatesExisting(t *testing.T) {
	db := newTestDB(t)
	if err := BatchUpsert(db, []DeviceStatus{{"car-001", "online", 10}}); err != nil {
		t.Fatal(err)
	}
	if err := BatchUpsert(db, []DeviceStatus{{"car-001", "offline", 5}}); err != nil {
		t.Fatal(err)
	}
	n, _ := count(db)
	if n != 1 {
		t.Fatalf("count = %d, want 1（upsert 不新增）", n)
	}
	var status string
	var speed float64
	db.QueryRow("SELECT status, speed FROM device_status WHERE device_id='car-001'").Scan(&status, &speed)
	if status != "offline" || speed != 5 {
		t.Errorf("upsert 未覆盖旧值: status=%s speed=%v", status, speed)
	}
}

func TestBatchUpsertEmptyBatch(t *testing.T) {
	db := newTestDB(t)
	if err := BatchUpsert(db, []DeviceStatus{}); err != nil {
		t.Fatalf("空批次应直接提交成功: %v", err)
	}
	n, _ := count(db)
	if n != 0 {
		t.Errorf("count = %d, want 0", n)
	}
}
