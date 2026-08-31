// 来源：ph10-database 示例 3 —— 事务（提交与回滚 + 并发防超扣）
// 一句话说明：转账的 Begin/Commit/Rollback 三阶段 + defer tx.Rollback() 防悬挂事务；
// 并发扣款用"条件更新"（UPDATE ... WHERE balance >= ?）原子防超扣——
// SQLite 不支持 MySQL 的 SELECT ... FOR UPDATE，条件更新是跨库通用的替代方案。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...          # 含并发防超扣用例（go test -race ./... 亦可）
//	go run .                  # 演示提交路径 + 回滚路径
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0）
package main

import (
	"database/sql"
	"fmt"
	"log"

	_ "modernc.org/sqlite"
)

// newAccountsDB 打开文件库并建 accounts 表
func newAccountsDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS accounts (
		id       INTEGER PRIMARY KEY,
		username TEXT NOT NULL UNIQUE,
		balance  INTEGER NOT NULL DEFAULT 0
	)`); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// seedAccounts 初始化两个账户
func seedAccounts(db *sql.DB, alice, bob int64) error {
	_, err := db.Exec("DELETE FROM accounts")
	if err != nil {
		return err
	}
	_, err = db.Exec("INSERT INTO accounts (username, balance) VALUES ('alice', ?), ('bob', ?)", alice, bob)
	return err
}

// Transfer 转账：扣款 + 加款原子完成；余额不足则回滚。
// 防超扣策略（SQLite 兼容）：扣款用条件更新 UPDATE ... WHERE balance >= ?，
// RowsAffected==0 表示余额不足——条件在 SQL 里原子判断，并发下也不会超扣。
func Transfer(db *sql.DB, from, to string, amount int64) error {
	if amount <= 0 {
		return fmt.Errorf("转账金额必须为正: %d", amount)
	}
	tx, err := db.Begin() // ① 开启事务
	if err != nil {
		return err
	}
	defer tx.Rollback() // ② 兜底：Commit 前任何 return 都自动回滚

	// ③ 条件扣款：只有 balance >= amount 才扣，返回受影响行数
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
	// ④ 加款
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
	db, err := newAccountsDB("/tmp/ex03-transaction.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := seedAccounts(db, 1000, 500); err != nil {
		log.Fatal(err)
	}

	if err := Transfer(db, "alice", "bob", 200); err != nil {
		log.Fatal(err) // 提交路径
	}
	fmt.Println("转账成功: alice -200, bob +200")

	if err := Transfer(db, "alice", "bob", 99999); err != nil {
		fmt.Println("回滚路径:", err) // 余额不足 → 事务回滚
	}
	a, _ := balance(db, "alice")
	b, _ := balance(db, "bob")
	fmt.Printf("校验: alice=%d bob=%d（总和不变）\n", a, b)
}
