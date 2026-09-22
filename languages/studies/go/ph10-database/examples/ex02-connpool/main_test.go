package main

import (
	"database/sql"
	"fmt"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

// newTestDB 用 t.TempDir 的临时文件库，避免污染仓库
func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "test.db")
	db, err := newPooledDB(path)
	if err != nil {
		t.Fatalf("newPooledDB: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	if err := setup(db); err != nil {
		t.Fatalf("setup: %v", err)
	}
	return db
}

func TestPoolConfig(t *testing.T) {
	db := newTestDB(t)
	// 四个 Set 方法生效后，Stats 应反映配置
	s := db.Stats()
	if s.MaxOpenConnections != 10 {
		t.Errorf("MaxOpenConnections = %d, want 10", s.MaxOpenConnections)
	}
	// Ping 后至少 1 条空闲连接
	s = db.Stats()
	if s.OpenConnections < 1 {
		t.Errorf("OpenConnections = %d, want >= 1", s.OpenConnections)
	}
}

func TestInsertPrepared(t *testing.T) {
	db := newTestDB(t)
	if err := insertPrepared(db, []string{"a", "b", "c"}); err != nil {
		t.Fatalf("insertPrepared: %v", err)
	}
	var n int
	if err := db.QueryRow("SELECT COUNT(*) FROM items").Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 3 {
		t.Errorf("count = %d, want 3", n)
	}
}

func TestInsertPreparedRollbackOnError(t *testing.T) {
	db := newTestDB(t)
	// 第二条插入触发 CHECK 约束错误：预处理语句同样返回错误（插入本身无事务，前面的已提交）
	// 本用例只验证"错误被正确返回"，不验证回滚（回滚是 ex03 事务的职责）
	if _, err := db.Exec(`ALTER TABLE items ADD COLUMN flag INTEGER CHECK (flag > 0)`); err != nil {
		t.Fatal(err)
	}
	stmt, err := db.Prepare("INSERT INTO items (name, flag) VALUES (?, ?)")
	if err != nil {
		t.Fatal(err)
	}
	defer stmt.Close()
	if _, err := stmt.Exec("x", -1); err == nil {
		t.Error("CHECK 约束违规应返回错误")
	}
}

func TestInsertLoopSameResult(t *testing.T) {
	db := newTestDB(t)
	// 对照组：循环 Exec 与预处理结果一致（教学对照，性能差异用 Benchmark 看）
	if err := insertLoop(db, []string{"p", "q"}); err != nil {
		t.Fatalf("insertLoop: %v", err)
	}
	var n int
	db.QueryRow("SELECT COUNT(*) FROM items").Scan(&n)
	if n != 2 {
		t.Errorf("count = %d, want 2", n)
	}
}

func TestPoolStatsTracked(t *testing.T) {
	db := newTestDB(t)
	// 并发 20 个 goroutine 各插入一条：连接池应能复用连接（MaxOpenConns=10 排队不报错）
	done := make(chan error, 20)
	for i := 0; i < 20; i++ {
		go func(i int) {
			_, err := db.Exec("INSERT INTO items (name) VALUES (?)", fmt.Sprintf("g%d", i))
			done <- err
		}(i)
	}
	for i := 0; i < 20; i++ {
		if err := <-done; err != nil {
			t.Fatalf("并发插入失败: %v", err)
		}
	}
	var n int
	db.QueryRow("SELECT COUNT(*) FROM items").Scan(&n)
	if n != 20 {
		t.Errorf("count = %d, want 20", n)
	}
}
