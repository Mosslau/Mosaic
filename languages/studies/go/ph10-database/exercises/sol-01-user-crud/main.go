// 来源：ph10-database 练习 1 参考实现 —— 用户表 CRUD
// 一句话说明：database/sql + 参数化 SQL 的 users 表增删改查：LastInsertId 拿自增主键、
// sql.ErrNoRows 判"不存在"、RowsAffected()==0 判"更新/删除未命中"、重复 username 报错。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...
//	go run .
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

// User 用户
type User struct {
	ID       int64
	Username string
	Password string
}

// newDB 打开内存库并建表
func newDB() (*sql.DB, error) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		return nil, err
	}
	_, err = db.Exec(`CREATE TABLE users (
		id         INTEGER PRIMARY KEY,
		username   TEXT NOT NULL UNIQUE,
		password   TEXT NOT NULL,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`)
	if err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// create 参数化 INSERT；重复 username 触发 UNIQUE 约束错误返回
func create(db *sql.DB, u *User) error {
	res, err := db.Exec("INSERT INTO users (username, password) VALUES (?, ?)", u.Username, u.Password)
	if err != nil {
		return err
	}
	u.ID, err = res.LastInsertId()
	return err
}

// getByID 单行查询；查无记录返回 sql.ErrNoRows
func getByID(db *sql.DB, id int64) (*User, error) {
	u := &User{}
	err := db.QueryRow("SELECT id, username, password FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username, &u.Password)
	if err != nil {
		return nil, err
	}
	return u, nil
}

// updatePassword 参数化 UPDATE；返回是否命中（RowsAffected==0 即 id 不存在）
func updatePassword(db *sql.DB, id int64, pwd string) (bool, error) {
	res, err := db.Exec("UPDATE users SET password = ? WHERE id = ?", pwd, id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
}

// deleteByID 参数化 DELETE；返回是否命中
func deleteByID(db *sql.DB, id int64) (bool, error) {
	res, err := db.Exec("DELETE FROM users WHERE id = ?", id)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
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
	fmt.Println("创建:", u.ID)
	if ok, _ := updatePassword(db, u.ID, "new"); ok {
		fmt.Println("更新密码成功")
	}
	if ok, _ := deleteByID(db, u.ID); ok {
		fmt.Println("删除成功")
	}
	_, err = getByID(db, 999)
	fmt.Println("查不存在记录:", errors.Is(err, sql.ErrNoRows))
}
