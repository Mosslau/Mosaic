// 来源：ph10-database 练习 2 参考实现 —— 设备状态存储（批量 UPSERT + 事务回滚）
// 一句话说明：一批设备状态在一个事务里写入——全部成功才 Commit、任一条非法（device_id 为空）
// 整批回滚；SQLite 的 ON CONFLICT(device_id) DO UPDATE 实现 upsert（MySQL 是 ON DUPLICATE KEY UPDATE）。
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

// DeviceStatus 设备状态
type DeviceStatus struct {
	DeviceID string
	Status   string
	Speed    float64
}

// newDB 打开内存库并建表（device_id 是主键，天然 UNIQUE，upsert 依赖它）
func newDB() (*sql.DB, error) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		return nil, err
	}
	_, err = db.Exec(`CREATE TABLE device_status (
		device_id  TEXT PRIMARY KEY,
		status     TEXT NOT NULL,
		speed      REAL NOT NULL DEFAULT 0,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`)
	if err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// BatchUpsert 批量写入：事务边界由业务定义——一批就是一个业务操作，任一条失败整体回滚
func BatchUpsert(db *sql.DB, items []DeviceStatus) error {
	tx, err := db.Begin() // ① 开启事务
	if err != nil {
		return err
	}
	defer tx.Rollback() // ② 兜底：Commit 前任何 return 都回滚
	for _, it := range items {
		if it.DeviceID == "" {
			return errors.New("device_id 不能为空") // ③ 中间出错 → defer 回滚整批
		}
		_, err := tx.Exec(
			`INSERT INTO device_status (device_id, status, speed) VALUES (?, ?, ?)
			 ON CONFLICT(device_id) DO UPDATE SET status = excluded.status, speed = excluded.speed`,
			it.DeviceID, it.Status, it.Speed)
		if err != nil {
			return err
		}
	}
	return tx.Commit() // ④ 全部成功才提交
}

// count 查总数（测试断言用）
func count(db *sql.DB) (int64, error) {
	var n int64
	err := db.QueryRow("SELECT COUNT(*) FROM device_status").Scan(&n)
	return n, err
}

func main() {
	db, err := newDB()
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	ok := []DeviceStatus{{"car-001", "online", 88.5}, {"car-002", "online", 60}}
	fail := []DeviceStatus{{"car-003", "online", 0}, {"", "offline", 0}}
	if err := BatchUpsert(db, ok); err != nil {
		log.Fatal(err)
	}
	fmt.Println("批量写入成功（2 条）")
	if err := BatchUpsert(db, fail); err != nil {
		fmt.Println("批量写入失败，已整体回滚:", err)
	}
	n, _ := count(db)
	fmt.Println("总条数（应仍为 2）:", n)
}
