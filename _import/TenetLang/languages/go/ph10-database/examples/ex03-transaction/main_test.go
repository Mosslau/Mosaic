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
	if err := seedAccounts(db, alice, bob); err != nil {
		t.Fatalf("seedAccounts: %v", err)
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
	// 回滚路径：两笔 UPDATE 都不生效
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

func TestTransferMissingAccount(t *testing.T) {
	db := newTestAccounts(t, 1000, 500)
	// 加款目标不存在：条件更新不报错（UPDATE 匹配 0 行），但转出方应已扣款——由调用方校验
	if err := Transfer(db, "alice", "ghost", 100); err != nil {
		t.Fatalf("Transfer: %v", err)
	}
	a, _ := balance(db, "alice")
	if a != 900 {
		t.Errorf("alice=%d, want 900（ghost 不存在时转出已扣款，这是教学演示的边界）", a)
	}
}

// TestConcurrentNoOverdraw 并发转账防超扣：10 个 goroutine 各转 100，
// alice 只有 1000——条件更新保证最多成功 10 笔，余额绝不小于 0
func TestConcurrentNoOverdraw(t *testing.T) {
	db := newTestAccounts(t, 1000, 0)
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = Transfer(db, "alice", "bob", 100) // 并发调用，错误可忽略（余额不足会失败）
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
		t.Errorf("总和 alice+bob = %d, want 1000（钱凭空多出来/消失了）", a+b)
	}
	t.Logf("并发后 alice=%d bob=%d（成功 %d 笔）", a, b, (1000-a)/100)
}
