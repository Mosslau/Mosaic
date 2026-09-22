package main

import (
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestConcurrent(t *testing.T) *sql.DB {
	t.Helper()
	db, err := newConcurrentDB(filepath.Join(t.TempDir(), "conc.db"))
	if err != nil {
		t.Fatalf("newConcurrentDB: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestSingleWriteAndCount(t *testing.T) {
	db := newTestConcurrent(t)
	if err := writeReading(db, "dev-1", 1.5); err != nil {
		t.Fatalf("writeReading: %v", err)
	}
	n, err := countReadings(db)
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Errorf("count = %d, want 1", n)
	}
}

// TestConcurrentWriters 并发写：20 goroutine × 10 条 = 200 条，一条不丢
// busy_timeout + WAL 保证写冲突时排队而不是失败
func TestConcurrentWriters(t *testing.T) {
	db := newTestConcurrent(t)
	if err := runConcurrent(db, 20, 10); err != nil {
		t.Fatalf("runConcurrent: %v", err)
	}
	n, err := countReadings(db)
	if err != nil {
		t.Fatal(err)
	}
	if n != 200 {
		t.Errorf("count = %d, want 200（并发写入有丢数据）", n)
	}
}

// TestConcurrentNoDataRace 交给 -race 验证；本用例保证功能正确
func TestConcurrentNoDataRace(t *testing.T) {
	db := newTestConcurrent(t)
	if err := runConcurrent(db, 8, 5); err != nil {
		t.Fatalf("runConcurrent: %v", err)
	}
}

func TestWALModeEnabled(t *testing.T) {
	db := newTestConcurrent(t)
	// journal_mode 应是 wal（DSN 里 _pragma=journal_mode(WAL) 生效）
	var mode string
	if err := db.QueryRow("PRAGMA journal_mode").Scan(&mode); err != nil {
		t.Fatal(err)
	}
	if mode != "wal" {
		t.Errorf("journal_mode = %q, want wal", mode)
	}
}
