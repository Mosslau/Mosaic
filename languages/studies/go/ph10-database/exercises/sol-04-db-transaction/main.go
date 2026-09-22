// 来源：ph10-database 练习 4 参考实现 —— 数据库事务处理（转账提交/回滚 + 并发防超扣）
// 一句话说明：Transfer 的 Begin/Commit/Rollback 三阶段 + defer 回滚兜底；防超扣用
// 条件更新（UPDATE ... WHERE balance >= ?）——SQLite 不支持 FOR UPDATE，条件更新是
// 跨库通用方案；busy_timeout 让并发写排队而非报 database is locked。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go run .
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0，-race 干净）
package main

import (
	"database/sql"
	"fmt"
	"log"
	"path/filepath"

	_ "modernc.org/sqlite"
)

// newAccountsDB 打开文件库（busy_timeout 防并发锁冲突）并建表
func newAccountsDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS accounts (
		username TEXT PRIMARY KEY,
		balance  INTEGER NOT NULL
	)`); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// seed 初始化账户（测试用）
func seed(db *sql.DB, alice, bob int64) error {
	if _, err := db.Exec("DELETE FROM accounts"); err != nil {
		return err
	}
	_, err := db.Exec("INSERT INTO accounts (username, balance) VALUES ('alice', ?), ('bob', ?)", alice, bob)
	return err
}

// Transfer 转账：条件扣款 + 加款，任一步失败整体回滚
func Transfer(db *sql.DB, from, to string, amount int64) error {
	if amount <= 0 {
		return fmt.Errorf("转账金额必须为正: %d", amount)
	}
	tx, err := db.Begin() // ① 开启事务
	if err != nil {
		return err
	}
	defer tx.Rollback() // ② 兜底：Commit 前任何 return 都回滚

	// ③ 条件扣款：只有 balance >= amount 才扣（原子判断，并发不超扣）
	res, err := tx.Exec("UPDATE accounts SET balance = balance - ? WHERE username = ? AND balance >= ?",
		amount, from, amount)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return fmt.Errorf("余额不足: %s", from)
	}
	// ④ 加款（目标账户不存在时匹配 0 行，不报错；业务侧自行决定是否校验）
	if _, err := tx.Exec("UPDATE accounts SET balance = balance + ? WHERE username = ?", amount, to); err != nil {
		return err
	}
	return tx.Commit() // ⑤ 全部成功才提交
}

// balance 查余额（测试断言用）
func balance(db *sql.DB, username string) (int64, error) {
	var b int64
	err := db.QueryRow("SELECT balance FROM accounts WHERE username = ?", username).Scan(&b)
	return b, err
}

func main() {
	db, err := newAccountsDB(filepath.Join("/tmp", "sol-04-transaction.db"))
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := seed(db, 1000, 500); err != nil {
		log.Fatal(err)
	}
	if err := Transfer(db, "alice", "bob", 200); err != nil {
		log.Fatal(err)
	}
	fmt.Println("转账成功: alice -200, bob +200")
	if err := Transfer(db, "alice", "bob", 99999); err != nil {
		fmt.Println("回滚路径:", err)
	}
	a, _ := balance(db, "alice")
	b, _ := balance(db, "bob")
	fmt.Printf("校验: alice=%d bob=%d（总和不变）\n", a, b)
}
