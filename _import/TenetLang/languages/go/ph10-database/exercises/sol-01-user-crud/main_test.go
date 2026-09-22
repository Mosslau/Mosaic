package main

import (
	"database/sql"
	"errors"
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

func TestCreateReturnsAutoID(t *testing.T) {
	db := newTestDB(t)
	u := &User{Username: "alice", Password: "p"}
	if err := create(db, u); err != nil {
		t.Fatalf("create: %v", err)
	}
	if u.ID == 0 {
		t.Error("LastInsertId 应返回自增主键")
	}
}

func TestGetByID(t *testing.T) {
	db := newTestDB(t)
	u := &User{Username: "alice", Password: "p"}
	if err := create(db, u); err != nil {
		t.Fatal(err)
	}
	got, err := getByID(db, u.ID)
	if err != nil {
		t.Fatalf("getByID: %v", err)
	}
	if got.Username != "alice" || got.Password != "p" {
		t.Errorf("got %+v", got)
	}
}

func TestGetMissingReturnsErrNoRows(t *testing.T) {
	db := newTestDB(t)
	_, err := getByID(db, 999)
	if !errors.Is(err, sql.ErrNoRows) {
		t.Errorf("want sql.ErrNoRows, got %v", err)
	}
}

func TestCreateDuplicateUsername(t *testing.T) {
	db := newTestDB(t)
	if err := create(db, &User{Username: "alice", Password: "a"}); err != nil {
		t.Fatal(err)
	}
	if err := create(db, &User{Username: "alice", Password: "b"}); err == nil {
		t.Error("重复 username 应插入失败（UNIQUE 约束）")
	}
}

func TestUpdatePasswordHitAndMiss(t *testing.T) {
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
	// 更新不存在的 id：RowsAffected==0 → 返回 false 而非报错
	if ok, _ := updatePassword(db, 999, "z"); ok {
		t.Error("更新不存在 id 应返回 false")
	}
}

func TestDeleteHitAndMiss(t *testing.T) {
	db := newTestDB(t)
	u := &User{Username: "carol", Password: "c"}
	if err := create(db, u); err != nil {
		t.Fatal(err)
	}
	if ok, _ := deleteByID(db, u.ID); !ok {
		t.Error("删除存在记录应返回 true")
	}
	if ok, _ := deleteByID(db, u.ID); ok {
		t.Error("重复删除应返回 false")
	}
}
