// 来源：ph10-database 示例 2 —— 连接池配置与预处理语句
// 一句话说明：database/sql 内置连接池的四个 Set 方法（MaxOpen/MaxIdle/ConnMaxLifetime/
// ConnMaxIdleTime）、db.Stats() 观测连接状态，以及 db.Prepare 预处理语句做批量插入。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...
//	go run .            # 用文件库演示 Stats 变化 + Prepare 批量插入
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0）
package main

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "modernc.org/sqlite"
)

// newPooledDB 打开 SQLite 文件库并配置连接池四个参数
// 注意：DSN 用 file: 前缀 + _pragma=busy_timeout(5000)（SQLite 并发写要设忙等待超时）
func newPooledDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(10)                  // 最大打开连接数（含使用中）——并发上限
	db.SetMaxIdleConns(5)                   // 最大空闲连接数（常驻待命，减少建连开销）
	db.SetConnMaxLifetime(30 * time.Minute) // 单条连接最长存活（防"连接老化"）
	db.SetConnMaxIdleTime(5 * time.Minute)  // 空闲超时即回收
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// setup 建表（幂等）
func setup(db *sql.DB) error {
	_, err := db.Exec(`CREATE TABLE IF NOT EXISTS items (
		id   INTEGER PRIMARY KEY,
		name TEXT NOT NULL
	)`)
	return err
}

// insertPrepared 用预处理语句批量插入：SQL 只编译一次，循环里只传参数
func insertPrepared(db *sql.DB, names []string) error {
	stmt, err := db.Prepare("INSERT INTO items (name) VALUES (?)") // ① 预编译
	if err != nil {
		return err
	}
	defer stmt.Close() // ② 用完必须关，否则占用连接
	for _, n := range names {
		if _, err := stmt.Exec(n); err != nil { // ③ 循环里只传值
			return err
		}
	}
	return nil
}

// insertLoop 对照组：循环里直接 Exec（每次都会隐式 prepare，慢）
func insertLoop(db *sql.DB, names []string) error {
	for _, n := range names {
		if _, err := db.Exec("INSERT INTO items (name) VALUES (?)", n); err != nil {
			return err
		}
	}
	return nil
}

func main() {
	db, err := newPooledDB("/tmp/ex02-connpool.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := setup(db); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("初始 Stats: %+v\n", db.Stats())

	if err := insertPrepared(db, []string{"a", "b", "c", "d", "e"}); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("插入 5 条后 Stats: %+v\n", db.Stats())

	var n int
	db.QueryRow("SELECT COUNT(*) FROM items").Scan(&n)
	fmt.Println("总数:", n)
}
