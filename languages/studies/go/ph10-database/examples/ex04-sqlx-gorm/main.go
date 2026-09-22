// 来源：ph10-database 示例 4 —— sqlx 增强与 GORM 选型对比
// 一句话说明：同一张 users 表，用 database/sql、sqlx（StructScan 结构体扫描）和
// GORM（全功能 ORM，链式 API + AutoMigrate）三种方式访问，对比学习成本与能力边界。
// 验证环境：go1.25.6（darwin/arm64），依赖：github.com/jmoiron/sqlx v1.4.0、
// gorm.io/gorm v1.31.2 + github.com/glebarez/sqlite v1.11.0（GORM 纯 Go 驱动）
// 运行：
//
//	go test -v ./...
//	go run .            # 顺序演示 database/sql → sqlx → GORM 三种写法
//
// 验证状态：已验证（go1.25.6 + sqlx v1.4.0 + gorm v1.31.2）
package main

import (
	"fmt"
	"log"

	"github.com/glebarez/sqlite"
	"github.com/jmoiron/sqlx"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// User database/sql 版：手写 Scan 目标
type User struct {
	ID       int64
	Username string
	Password string
}

// UserRow sqlx 版：db tag 驱动列映射
type UserRow struct {
	ID       int64  `db:"id"`
	Username string `db:"username"`
	Password string `db:"password"`
}

// UserGorm GORM 版：gorm tag 驱动建表与映射
type UserGorm struct {
	ID       int64  `gorm:"primaryKey"`
	Username string `gorm:"uniqueIndex;not null"`
	Password string `gorm:"not null"`
}

// viaDatabaseSQL 原生 database/sql：连接池/事务/参数化全有，但列映射要手写。
// sqlx.DB 内嵌 *sql.DB，QueryRow/Scan 是标准库原样能力。
func viaDatabaseSQL(db *sqlx.DB) {
	var u User
	err := db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", 1).
		Scan(&u.ID, &u.Username, &u.Password) // 手写 Scan：列多了就啰嗦
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("[database/sql] user: %+v\n", u)
}

// sqlxOpen 打开 sqlx 连接（db tag 映射列到结构体）
func sqlxOpen(path string) (*sqlx.DB, error) {
	return sqlx.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)")
}

// viaSQLx 用 sqlx 的 Select/Get + StructScan：Rows.Scan 样板代码被压缩
func viaSQLx(db *sqlx.DB) {
	var users []UserRow
	if err := db.Select(&users, "SELECT id, username, password FROM users ORDER BY id"); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("[sqlx Select] %+v\n", users)
}

// viaGORM GORM：AutoMigrate 自动建表 + 链式 API
func viaGORM(path string) {
	gdb, err := gorm.Open(sqlite.Open("file:"+path+"?_pragma=busy_timeout(5000)"),
		&gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		log.Fatal(err)
	}
	if err := gdb.AutoMigrate(&UserGorm{}); err != nil {
		log.Fatal(err)
	}
	// 用 GORM 再插一条，展示 ORM 的 Create
	if err := gdb.Create(&UserGorm{Username: "carol", Password: "c"}).Error; err != nil {
		log.Fatal(err)
	}
	var u UserGorm
	if err := gdb.First(&u, "username = ?", "carol").Error; err != nil {
		log.Fatal(err)
	}
	fmt.Printf("[GORM First] %+v\n", u)
}

func main() {
	path := "/tmp/ex04-sqlx-gorm.db"
	// 建表 + 塞数据（用 sqlx 完成准备工作）
	base, err := sqlxOpen(path)
	if err != nil {
		log.Fatal(err)
	}
	base.MustExec(`DROP TABLE IF EXISTS users`)
	base.MustExec(`CREATE TABLE users (
		id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL)`)
	base.MustExec(`INSERT INTO users (username, password) VALUES ('alice','a'), ('bob','b')`)
	base.Close()

	sqlxDB, err := sqlxOpen(path) // 重新打开：连接不跨 Open 共享
	if err != nil {
		log.Fatal(err)
	}
	defer sqlxDB.Close()
	viaDatabaseSQL(sqlxDB)
	viaSQLx(sqlxDB)
	viaGORM(path)
}
