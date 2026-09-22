package main

import (
	"database/sql"
	"errors"
	"strings"
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

func TestCreateGet(t *testing.T) {
	db := newTestDB(t)
	u := &User{Username: "alice", Password: "p@ss"}
	if err := create(db, u); err != nil {
		t.Fatalf("create: %v", err)
	}
	if u.ID == 0 {
		t.Error("LastInsertId 应返回自增主键")
	}
	got, err := getByID(db, u.ID)
	if err != nil {
		t.Fatalf("getByID: %v", err)
	}
	if got.Username != "alice" {
		t.Errorf("got username %q, want alice", got.Username)
	}
}

func TestGetMissingReturnsErrNoRows(t *testing.T) {
	db := newTestDB(t)
	_, err := getByID(db, 999)
	if !errors.Is(err, sql.ErrNoRows) {
		t.Errorf("want sql.ErrNoRows, got %v", err)
	}
}

func TestCreateDuplicateUsernameFails(t *testing.T) {
	db := newTestDB(t)
	if err := create(db, &User{Username: "alice", Password: "a"}); err != nil {
		t.Fatalf("first create: %v", err)
	}
	// UNIQUE 约束：重复用户名插入失败（参数化能防注入，但约束错误仍要处理）
	if err := create(db, &User{Username: "alice", Password: "b"}); err == nil {
		t.Error("重复 username 应插入失败")
	}
}

func TestUpdateAndDelete(t *testing.T) {
	db := newTestDB(t)
	u := &User{Username: "bob", Password: "x"}
	if err := create(db, u); err != nil {
		t.Fatal(err)
	}
	ok, err := updatePassword(db, u.ID, "y")
	if err != nil || !ok {
		t.Fatalf("update ok=%v err=%v", ok, err)
	}
	got, _ := getByID(db, u.ID)
	if got.Password != "y" {
		t.Errorf("password = %q, want y", got.Password)
	}
	// 更新不存在的 id：RowsAffected==0
	if ok, _ := updatePassword(db, 999, "z"); ok {
		t.Error("更新不存在 id 应返回 false")
	}
	if ok, _ := deleteByID(db, u.ID); !ok {
		t.Error("删除存在记录应返回 true")
	}
	if ok, _ := deleteByID(db, u.ID); ok {
		t.Error("重复删除应返回 false")
	}
}

func TestListAll(t *testing.T) {
	db := newTestDB(t)
	for _, name := range []string{"a", "b", "c"} {
		if err := create(db, &User{Username: name, Password: "p"}); err != nil {
			t.Fatal(err)
		}
	}
	users, err := listAll(db)
	if err != nil {
		t.Fatal(err)
	}
	if len(users) != 3 {
		t.Errorf("len = %d, want 3", len(users))
	}
	if users[0].Username != "a" || users[2].Username != "c" {
		t.Errorf("顺序错误: %+v", users)
	}
}

func TestExplainIndex(t *testing.T) {
	db := newTestDB(t)
	if err := create(db, &User{Username: "alice", Password: "p"}); err != nil {
		t.Fatal(err)
	}
	detail := explainIndex(db, "alice")
	// username 有 UNIQUE 索引，执行计划应使用索引（现代 SQLite 输出 "USING INDEX" 或 "COVERING INDEX"）
	if !strings.Contains(detail, "INDEX") {
		t.Errorf("执行计划未走索引: %s", detail)
	}
	t.Logf("EXPLAIN QUERY PLAN: %s", detail)
}
