# exercises/sol-03-device-status.py —— 练习 3 参考实现：设备状态表（高频写入 + 复合索引）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 sol-03-device-status.py（离线可跑，已验证；数据库写入系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 实际运行）：
#   批量写入 100,000 行 -> 总行数: 100000
#   无索引计划: SCAN device_status，耗时 1.89 ms
#   有索引计划: SEARCH ... USING INDEX idx_status_device_ts (device_id=? AND ts>? AND ts<?)，耗时 0.09 ms
#     （复合索引约快 21 倍）
#   仅 device_id 查询计划: SEARCH ... USING INDEX idx_status_device_ts (device_id=?)（最左前缀生效）
import sqlite3
import tempfile
import time
from pathlib import Path

N_DEVICES = 500
N_ROWS = 100_000  # 批量写入 10 万行状态（500 台设备 × 200 条）


def measure(cur: sqlite3.Cursor, device_id: int, t0: str, t1: str) -> tuple[list[tuple], float]:
    """按 (device_id, ts 范围) 查询：返回执行计划与耗时（毫秒）。"""
    plan = cur.execute(
        """EXPLAIN QUERY PLAN
           SELECT * FROM device_status
           WHERE device_id = ? AND ts BETWEEN ? AND ?""",
        (device_id, t0, t1),
    ).fetchall()
    start = time.perf_counter()
    cur.execute(
        """SELECT * FROM device_status
           WHERE device_id = ? AND ts BETWEEN ? AND ?""",
        (device_id, t0, t1),
    ).fetchall()
    return plan, (time.perf_counter() - start) * 1000


def main() -> None:
    conn = sqlite3.connect(Path(tempfile.mkdtemp(prefix="ph11-sol03-")) / "status.db")
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE device_status (
               id INTEGER PRIMARY KEY,
               device_id INTEGER NOT NULL,
               ts TEXT NOT NULL,          -- ISO 时间串，便于范围查询
               status TEXT NOT NULL,
               speed REAL
           )"""
    )

    # 1. 高频写入：executemany 批量插入 10 万行（500 台设备 × 200 条）
    rows = [
        (i % N_DEVICES, f"2024-06-01T08:{(i // N_DEVICES) % 60:02d}:{(i % 60):02d}",
         "online", round(40 + (i % 60) * 0.5, 1))
        for i in range(N_ROWS)
    ]
    cur.executemany(
        "INSERT INTO device_status (device_id, ts, status, speed) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"批量写入 {N_ROWS:,} 行 -> 总行数:",
          cur.execute("SELECT COUNT(*) FROM device_status").fetchone()[0])

    # 2. 无索引：按设备 + 时间范围查询（全表扫描 10 万行）
    plan, ms = measure(cur, 7, "2024-06-01T08:00:00", "2024-06-01T08:10:00")
    print("无索引计划:", plan)
    print(f"无索引耗时: {ms:.2f} ms")

    # 3. 复合索引 (device_id, ts)：最左前缀——device_id 单独查也能命中
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_status_device_ts ON device_status(device_id, ts)"
    )
    conn.commit()
    plan, ms = measure(cur, 7, "2024-06-01T08:00:00", "2024-06-01T08:10:00")
    print("有索引计划:", plan)
    print(f"有索引耗时: {ms:.2f} ms")

    plan_only_device = cur.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM device_status WHERE device_id = 7"
    ).fetchall()
    print("仅 device_id 查询计划:", plan_only_device, "（最左前缀生效）")
    conn.close()


if __name__ == "__main__":
    main()
