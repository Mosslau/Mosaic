# examples/ex03-index-query-plan.py —— 索引与查询优化：EXPLAIN QUERY PLAN + 实测耗时对比
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex03-index-query-plan.py（离线可跑，已验证；数据库写入系统临时目录）
# 说明：对应主文档 3.5/4.1。两万行数据按 device_id 精确查询：先看全表扫描的执行计划与耗时，
#       加索引后再对比——执行计划从 SCAN 变 SEARCH，耗时下降。
import sqlite3
import tempfile
import time
from pathlib import Path

DB_PATH = Path(tempfile.mkdtemp(prefix="ph11-ex03-")) / "perf.db"
N_ROWS = 20_000


def setup(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS devices (
               id INTEGER PRIMARY KEY, device_id TEXT, model TEXT, online INTEGER
           )"""
    )
    cur.execute("DELETE FROM devices")
    cur.executemany(
        "INSERT INTO devices (device_id, model, online) VALUES (?, ?, ?)",
        [(f"DEVICE_ID{i:06d}", f"EV-{i % 5}", i % 2) for i in range(N_ROWS)],
    )


def measure(cur: sqlite3.Cursor, device_id: str) -> tuple[list[tuple], float]:
    """返回执行计划与一次查询耗时（毫秒）。"""
    plan = cur.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM devices WHERE device_id = ?", (device_id,)
    ).fetchall()
    t0 = time.perf_counter()
    cur.execute(
        "SELECT * FROM devices WHERE device_id = ?", (device_id,)
    ).fetchall()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return plan, elapsed_ms


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    setup(cur)
    conn.commit()

    device_id = "DEVICE_ID000123"  # 目标行存在于 20_000 行数据中

    print(f"--- 无索引（{N_ROWS:,} 行全表扫描）---")
    plan, ms = measure(cur, device_id)
    print("执行计划:", plan)
    print(f"耗时: {ms:.2f} ms")

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)"
    )
    conn.commit()

    print("--- 有索引 ---")
    plan, ms = measure(cur, device_id)
    print("执行计划:", plan)
    print(f"耗时: {ms:.2f} ms")

    conn.close()
    print("数据库文件:", DB_PATH)


if __name__ == "__main__":
    main()
