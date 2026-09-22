// 来源：ph10-database 示例 1 —— SQL 基础与 database/sql CRUD
// 一句话说明：users 表的参数化增删改查（C: INSERT+LastInsertId / R: QueryRow+Scan /
// Q: Query+Rows 循环 / U: Exec / D: Exec），覆盖 sql.ErrNoRows、索引与 EXPLAIN QUERY PLAN。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...
//	go run .            # 使用内存库 :memory:，打印 CRUD 全流程
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0）
package main

import (
	"database/sql"
	"errors"
	"fmt"
	"log"

	_ "modernc.org/sqlite"
)

// User 对应 users 表一行
type User struct {
	ID       int64
	Username string
	Password string
}

// newDB 打开 SQLite 内存库并建表（生产用文件路径，如 "file:app.db?_pragma=busy_timeout(5000)"）
func newDB() (*sql.DB, error) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`CREATE TABLE users (
		id         INTEGER PRIMARY KEY,
		username   TEXT NOT NULL UNIQUE,
		password   TEXT NOT NULL,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// create 参数化 INSERT，LastInsertId 拿自增主键（SQLite 的 INTEGER PRIMARY KEY 即自增）
func create(db *sql.DB, u *User) error {
	res, err := db.Exec("INSERT INTO users (username, password) VALUES (?, ?)", u.Username, u.Password)
	if err != nil {
		return err
	}
	u.ID, err = res.LastInsertId()
	return err
}

// getByID 单行查询；查无记录返回 sql.ErrNoRows（唯一正确的"不存在"判定）
func getByID(db *sql.DB, id int64) (*User, error) {
	u := &User{}
	err := db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username, &u.Password)
	if err != nil {
		return nil, err
	}
	return u, nil
}

// listAll 多行查询：Rows 遍历 + defer rows.Close()（连接借了必须还）
func listAll(db *sql.DB) ([]User, error) {
	rows, err := db.Query("SELECT id, username, password FROM users ORDER BY id")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	users := make([]User, 0)
	for rows.Next() {
		var u User
		if err := rows.Scan(&u.ID, &u.Username, &u.Password); err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, rows.Err() // 遍历结束后还要查一次 rows.Err()
}

// updatePassword 参数化 UPDATE；RowsAffected==0 表示 id 不存在（更新未命中）
func updatePassword(db *sql.DB, id int64, pwd string) (bool, error) {
	res, err := db.Exec("UPDATE users SET password = ? WHERE id = ?", pwd, id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
}

// deleteByID 参数化 DELETE，同样用 RowsAffected 判定是否存在
func deleteByID(db *sql.DB, id int64) (bool, error) {
	res, err := db.Exec("DELETE FROM users WHERE id = ?", id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
}

// explainIndex 用 EXPLAIN QUERY PLAN 观察索引命中（SQLite 的"执行计划"；MySQL 用 EXPLAIN）
// 注：EXPLAIN QUERY PLAN 返回 4 列，这里只取第 4 列 detail（描述文本）
func explainIndex(db *sql.DB, username string) string {
	rows, err := db.Query("EXPLAIN QUERY PLAN SELECT id FROM users WHERE username = ?", username)
	if err != nil {
		return "EXPLAIN 失败: " + err.Error()
	}
	defer rows.Close()
	var detail string
	for rows.Next() {
		var id, parent, notused int
		if err := rows.Scan(&id, &parent, &notused, &detail); err != nil {
			return "EXPLAIN 失败: " + err.Error()
		}
	}
	return detail
}

func main() {
	db, err := newDB()
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	u := &User{Username: "alice", Password: "p@ss"}
	if err := create(db, u); err != nil {
		log.Fatal(err)
	}
	fmt.Println("创建:", u.ID, u.Username)

	got, err := getByID(db, u.ID)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("查询: id=%d username=%s\n", got.ID, got.Username)

	if ok, _ := updatePassword(db, u.ID, "new-pwd"); ok {
		fmt.Println("更新密码成功")
	}

	users, err := listAll(db)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("列表: %d 条\n", len(users))

	// 查不存在的记录 → sql.ErrNoRows
	_, err = getByID(db, 999)
	fmt.Println("查无记录:", errors.Is(err, sql.ErrNoRows))

	if ok, _ := deleteByID(db, u.ID); ok {
		fmt.Println("删除成功")
	}
	fmt.Println("执行计划:", explainIndex(db, "alice"))
}
