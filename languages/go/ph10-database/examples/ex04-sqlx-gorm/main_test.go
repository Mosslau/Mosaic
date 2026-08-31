package main

import (
	"path/filepath"
	"testing"

	"github.com/glebarez/sqlite"
	"github.com/jmoiron/sqlx"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// setupSQLx 建表 + 塞数据，返回可用的 sqlx 连接
func setupSQLx(t *testing.T) *sqlx.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "users.db")
	db, err := sqlxOpen(path)
	if err != nil {
		t.Fatalf("sqlxOpen: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	db.MustExec(`CREATE TABLE users (
		id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL)`)
	db.MustExec(`INSERT INTO users (username, password) VALUES ('alice','a'), ('bob','b')`)
	return db
}

func TestDatabaseSQLScan(t *testing.T) {
	db := setupSQLx(t)
	var u User
	if err := db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", 1).
		Scan(&u.ID, &u.Username, &u.Password); err != nil {
		t.Fatalf("QueryRow.Scan: %v", err)
	}
	if u.Username != "alice" {
		t.Errorf("username = %q, want alice", u.Username)
	}
}

func TestSQLxStructScan(t *testing.T) {
	db := setupSQLx(t)
	var rows []UserRow
	if err := db.Select(&rows, "SELECT id, username, password FROM users ORDER BY id"); err != nil {
		t.Fatalf("Select: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("len = %d, want 2", len(rows))
	}
	// db tag 把列映射进结构体：不需要手写 Scan
	if rows[0].Username != "alice" || rows[1].Username != "bob" {
		t.Errorf("rows = %+v", rows)
	}
}

func TestSQLxGetSingleRow(t *testing.T) {
	db := setupSQLx(t)
	var u UserRow
	// sqlx.Get 单行映射；查无记录返回 sql.ErrNoRows
	if err := db.Get(&u, "SELECT * FROM users WHERE username = ?", "bob"); err != nil {
		t.Fatalf("Get: %v", err)
	}
	if u.Username != "bob" {
		t.Errorf("username = %q, want bob", u.Username)
	}
}

func TestGORMCreateAndFirst(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gorm.db")
	gdb, err := gorm.Open(sqlite.Open("file:"+path+"?_pragma=busy_timeout(5000)"),
		&gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatalf("gorm.Open: %v", err)
	}
	if err := gdb.AutoMigrate(&UserGorm{}); err != nil {
		t.Fatalf("AutoMigrate: %v", err)
	}
	if err := gdb.Create(&UserGorm{Username: "carol", Password: "c"}).Error; err != nil {
		t.Fatalf("Create: %v", err)
	}
	var u UserGorm
	if err := gdb.First(&u, "username = ?", "carol").Error; err != nil {
		t.Fatalf("First: %v", err)
	}
	if u.ID == 0 || u.Username != "carol" {
		t.Errorf("First got %+v", u)
	}
	// 唯一索引：重复 username 报错（gorm 的 Updates 等行为差异是选型依据）
	if err := gdb.Create(&UserGorm{Username: "carol", Password: "x"}).Error; err == nil {
		t.Error("重复 username 应报错")
	}
}

func TestGORMCounts(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gorm.db")
	gdb, err := gorm.Open(sqlite.Open("file:"+path+"?_pragma=busy_timeout(5000)"),
		&gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	gdb.AutoMigrate(&UserGorm{})
	gdb.Create(&UserGorm{Username: "d", Password: "d"})
	gdb.Create(&UserGorm{Username: "e", Password: "e"})
	var count int64
	if err := gdb.Model(&UserGorm{}).Count(&count).Error; err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Errorf("count = %d, want 2", count)
	}
}

// TestViaFunctions 把三种 demo 访问函数串起来跑一遍（覆盖 main.go 的 via* 流程）
func TestViaFunctions(t *testing.T) {
	path := filepath.Join(t.TempDir(), "via.db")
	base, err := sqlxOpen(path)
	if err != nil {
		t.Fatal(err)
	}
	base.MustExec(`CREATE TABLE users (
		id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL)`)
	base.MustExec(`INSERT INTO users (username, password) VALUES ('alice','a'), ('bob','b')`)
	base.Close()

	sqlxDB, err := sqlxOpen(path)
	if err != nil {
		t.Fatal(err)
	}
	defer sqlxDB.Close()
	viaDatabaseSQL(sqlxDB) // 打印 demo（成功路径不触发 log.Fatal）
	viaSQLx(sqlxDB)
	viaGORM(path)
}
