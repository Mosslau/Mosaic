// 来源：ph10-database 示例 5 —— 并发访问数据库
// 一句话说明：多 goroutine 并发读写同一 SQLite 库——连接池负责连接复用与排队
// （SetMaxOpenConns 上限），DSN 的 busy_timeout 让写冲突时等待而非报错，
// WAL 模式让读不阻塞写。用 go test -race 验证无数据竞争。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./...
//	go test -race ./...   # 数据竞争检测
//	go run .              # 20 goroutine 并发写 + 并发读
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0，-race 干净）
package main

import (
	"database/sql"
	"fmt"
	"log"
	"sync"
	"time"

	_ "modernc.org/sqlite"
)

// newConcurrentDB 打开 WAL 模式 + busy_timeout 的 SQLite 文件库
// busy_timeout(5000)：写锁被占时等待最多 5 秒，而不是立即报 database is locked
func newConcurrentDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite",
		"file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8) // 并发上限：超过的请求排队，防连接风暴
	if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS readings (
		id      INTEGER PRIMARY KEY,
		device  TEXT NOT NULL,
		value   REAL NOT NULL,
		created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// writeReading 单条写入（并发调用方）
func writeReading(db *sql.DB, device string, value float64) error {
	_, err := db.Exec("INSERT INTO readings (device, value) VALUES (?, ?)", device, value)
	return err
}

// countReadings 并发读：COUNT 聚合
func countReadings(db *sql.DB) (int64, error) {
	var n int64
	err := db.QueryRow("SELECT COUNT(*) FROM readings").Scan(&n)
	return n, err
}

// runConcurrent 20 个写 goroutine + 2 个读 goroutine 同时跑
func runConcurrent(db *sql.DB, writers, perWriter int) error {
	var wg sync.WaitGroup
	errCh := make(chan error, writers+2)
	for w := 0; w < writers; w++ {
		wg.Add(1)
		go func(w int) { // goroutine 写
			defer wg.Done()
			for i := 0; i < perWriter; i++ {
				if err := writeReading(db, fmt.Sprintf("dev-%d", w), float64(i)); err != nil {
					errCh <- fmt.Errorf("write: %w", err)
					return
				}
			}
		}(w)
	}
	// 2 个读 goroutine
	for r := 0; r < 2; r++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 5; i++ {
				if _, err := countReadings(db); err != nil {
					errCh <- fmt.Errorf("read: %w", err)
					return
				}
			}
		}()
	}
	wg.Wait()
	close(errCh)
	for err := range errCh {
		return err
	}
	return nil
}

func main() {
	db, err := newConcurrentDB("/tmp/ex05-concurrent.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	start := time.Now()
	if err := runConcurrent(db, 20, 10); err != nil {
		log.Fatal(err)
	}
	n, _ := countReadings(db)
	fmt.Printf("并发写入完成: %d 条（20 goroutine × 10 条），耗时 %v\n", n, time.Since(start))
}
