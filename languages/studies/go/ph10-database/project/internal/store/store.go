// 来源：ph10-database 阶段项目 —— 车辆轨迹存储服务（internal/store 包）
// 一句话说明：SQLite 存储层——devices 与 gps_points 两张表、按"设备 + 时间"建索引、
// 批量上报走事务（全部成功才提交）、查最新位置/时间段轨迹；Store 接口隔离存储细节，
// api 层只依赖接口（ph08「接口有助于隔离测试依赖」落地）。
// 验证环境：go1.25.6（darwin/arm64），驱动：modernc.org/sqlite v1.57.0（纯 Go 无 cgo）
// 运行：
//
//	go test -v ./internal/store
//	go test -race ./internal/store
//
// 验证状态：已验证（go1.25.6 + modernc.org/sqlite v1.57.0）
package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	_ "modernc.org/sqlite"
)

// ErrDeviceNotFound 设备不存在
var ErrDeviceNotFound = errors.New("device not found")

// Point GPS 轨迹点
type Point struct {
	DeviceID string    `json:"device_id"`
	Lat      float64   `json:"lat"`
	Lng      float64   `json:"lng"`
	Speed    float64   `json:"speed"`
	TS       time.Time `json:"ts"`
}

// Store 轨迹数据访问接口：api 层只依赖它（ctx 贯穿，取消/超时可传进每条 SQL）
type Store interface {
	// UpsertDevice 注册设备（已存在则幂等）
	UpsertDevice(ctx context.Context, id string) error
	// BatchInsert 一批轨迹点写入（事务：全部成功才提交）
	BatchInsert(ctx context.Context, points []Point) error
	// Latest 查询设备最新位置（未上报过返回 ErrDeviceNotFound）
	Latest(ctx context.Context, deviceID string) (Point, error)
	// Trajectory 查询设备某时间段的轨迹（按时间升序）
	Trajectory(ctx context.Context, deviceID string, from, to time.Time) ([]Point, error)
}

// sqliteStore SQLite 实现
type sqliteStore struct {
	db *sql.DB
}

// Open 打开（或创建）SQLite 库并建表建索引，返回具体类型（调用方可 Close）
func Open(path string) (*sqliteStore, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS devices (
			id TEXT PRIMARY KEY,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
		);
		CREATE TABLE IF NOT EXISTS gps_points (
			id        INTEGER PRIMARY KEY,
			device_id TEXT NOT NULL,
			lat       REAL NOT NULL,
			lng       REAL NOT NULL,
			speed     REAL NOT NULL,
			ts        DATETIME NOT NULL,
			FOREIGN KEY (device_id) REFERENCES devices(id)
		);
		CREATE INDEX IF NOT EXISTS idx_points_device_ts ON gps_points (device_id, ts);`); err != nil {
		db.Close()
		return nil, err
	}
	return &sqliteStore{db: db}, nil
}

func (s *sqliteStore) UpsertDevice(ctx context.Context, id string) error {
	_, err := s.db.ExecContext(ctx, "INSERT INTO devices (id) VALUES (?) ON CONFLICT(id) DO NOTHING", id)
	return err
} // BatchInsert 事务批量写入：任一点失败整体回滚（呼应 3.6「事务边界由业务定义」）
func (s *sqliteStore) BatchInsert(ctx context.Context, points []Point) error {
	tx, err := s.db.BeginTx(ctx, nil) // BeginTx：context 的取消/超时贯穿事务
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, p := range points {
		if p.DeviceID == "" {
			return errors.New("device_id 不能为空")
		}
		// 设备不存在则先注册（简化：允许隐式建设备）
		if _, err := tx.ExecContext(ctx, "INSERT INTO devices (id) VALUES (?) ON CONFLICT(id) DO NOTHING", p.DeviceID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx,
			"INSERT INTO gps_points (device_id, lat, lng, speed, ts) VALUES (?, ?, ?, ?, ?)",
			p.DeviceID, p.Lat, p.Lng, p.Speed, p.TS.Format(time.RFC3339)); err != nil {
			return fmt.Errorf("insert point: %w", err)
		}
	}
	return tx.Commit()
}

func (s *sqliteStore) Latest(ctx context.Context, deviceID string) (Point, error) {
	var p Point
	var ts string
	err := s.db.QueryRowContext(ctx,
		"SELECT device_id, lat, lng, speed, ts FROM gps_points WHERE device_id = ? ORDER BY ts DESC, id DESC LIMIT 1",
		deviceID).Scan(&p.DeviceID, &p.Lat, &p.Lng, &p.Speed, &ts)
	if errors.Is(err, sql.ErrNoRows) {
		return Point{}, ErrDeviceNotFound
	}
	if err != nil {
		return Point{}, err
	}
	p.TS, err = time.Parse(time.RFC3339, ts)
	return p, err
}

func (s *sqliteStore) Trajectory(ctx context.Context, deviceID string, from, to time.Time) ([]Point, error) {
	rows, err := s.db.QueryContext(ctx,
		"SELECT device_id, lat, lng, speed, ts FROM gps_points WHERE device_id = ? AND ts >= ? AND ts <= ? ORDER BY ts ASC",
		deviceID, from.Format(time.RFC3339), to.Format(time.RFC3339))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	points := make([]Point, 0)
	for rows.Next() {
		var p Point
		var ts string
		if err := rows.Scan(&p.DeviceID, &p.Lat, &p.Lng, &p.Speed, &ts); err != nil {
			return nil, err
		}
		p.TS, err = time.Parse(time.RFC3339, ts)
		if err != nil {
			return nil, err
		}
		points = append(points, p)
	}
	return points, rows.Err()
}

// Close 关闭底层连接池
func (s *sqliteStore) Close() error { return s.db.Close() }
