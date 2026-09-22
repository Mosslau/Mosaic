package main

import (
	"database/sql"
	"path/filepath"
	"sync"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestAccounts(t *testing.T, alice, bob int64) *sql.DB {
	t.Helper()
	db, err := newAccountsDB(filepath.Join(t.TempDir(), "accounts.db"))
	if err != nil {
		t.Fatalf("newAccountsDB: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	if err := seed(db, alice, bob); err != nil {
		t.Fatalf("seed: %v", err)
	}
	return db
}

func TestTransferCommitPath(t *testing.T) {
	db := newTestAccounts(t, 1000, 500)
	if err := Transfer(db, "alice", "bob", 200); err != nil {
		t.Fatalf("Transfer: %v", err)
	}
	a, _ := balance(db, "alice")
	b, _ := balance(db, "bob")
	if a != 800 || b != 700 {
		t.Errorf("alice=%d bob=%d, want 800/700", a, b)
	}
}

func TestTransferRollbackOnInsufficient(t *testing.T) {
	db := newTestAccounts(t, 1000, 500)
	if err := Transfer(db, "alice", "bob", 99999); err == nil {
		t.Fatal("余额不足应返回错误")
	}
	a, _ := balance(db, "alice")
	b, _ := balance(db, "bob")
	if a != 1000 || b != 500 {
		t.Errorf("回滚后 alice=%d bob=%d, want 1000/500（总和不变）", a, b)
	}
}

func TestTransferInvalidAmount(t *testing.T) {
	db := newTestAccounts(t, 1000, 500)
	if err := Transfer(db, "alice", "bob", 0); err == nil {
		t.Error("金额为 0 应报错")
	}
	if err := Transfer(db, "alice", "bob", -5); err == nil {
		t.Error("金额为负应报错")
	}
}

// TestConcurrentNoOverdraw 并发防超扣：10 个 goroutine 各转 100，初始 1000——
// 条件更新保证最多成功 10 笔，余额总和不变、绝不为负
func TestConcurrentNoOverdraw(t *testing.T) {
	db := newTestAccounts(t, 1000, 0)
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = Transfer(db, "alice", "bob", 100)
		}()
	}
	wg.Wait()
	a, err := balance(db, "alice")
	if err != nil {
		t.Fatal(err)
	}
	b, _ := balance(db, "bob")
	if a < 0 {
		t.Errorf("alice 余额为负: %d（超扣了！）", a)
	}
	if a+b != 1000 {
		t.Errorf("总和 alice+bob = %d, want 1000", a+b)
	}
	t.Logf("并发后 alice=%d bob=%d（成功 %d 笔）", a, b, (1000-a)/100)
}
