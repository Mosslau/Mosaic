# exercises/sol-02-device-info.py —— 练习 2 参考实现：设备信息管理（device_id 唯一 + 索引）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 sol-02-device-info.py（离线可跑，已验证；数据库写入系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 实际运行）：
#   注册 2 台设备 -> 总行数: 2；重复 device_id -> UNIQUE constraint failed: devices.device_id
#   填充后总行数: 20002
#   device_id 查询计划（UNIQUE 自带索引）: SEARCH ... USING INDEX sqlite_autoindex_devices_1 (device_id=?)
#   model 查询（无索引）: SCAN devices 1.65 ms；（有索引）: SEARCH ... USING INDEX idx_devices_model 1.78 ms
#     （2 万行小表上耗时差异不明显——计划变化才是「走没走索引」的硬证据，见主文档 3.5「小表不加索引」）
import sqlite3
import tempfile
import time
from pathlib import Path


def main() -> None:
    conn = sqlite3.connect(Path(tempfile.mkdtemp(prefix="ph11-sol02-")) / "devices.db")
    conn.isolation_level = None  # 手动控制事务
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE devices (
               id INTEGER PRIMARY KEY,
               device_id TEXT NOT NULL UNIQUE,          -- device_id 唯一：同一台设备不能重复注册
               model TEXT NOT NULL,
               online INTEGER DEFAULT 0
           )"""
    )

    # 1. 注册设备 + 重复 device_id 拒绝
    for device_id, model in [("V001", "EV-A"), ("V002", "EV-B")]:
        cur.execute("BEGIN")
        cur.execute(
            "INSERT INTO devices (device_id, model) VALUES (?, ?)", (device_id, model)
        )
        cur.execute("COMMIT")
    print("注册 2 台设备 -> 总行数:",
          cur.execute("SELECT COUNT(*) FROM devices").fetchone()[0])

    try:
        cur.execute("BEGIN")
        cur.execute(
            "INSERT INTO devices (device_id, model) VALUES (?, ?)", ("V001", "EV-A")
        )
        cur.execute("COMMIT")
    except sqlite3.IntegrityError as e:
        cur.execute("ROLLBACK")
        print("重复 device_id ->", e)

    # 2. 填充 2 万行：model 是「非唯一列」——加普通索引前后对比执行计划
    cur.execute("BEGIN")
    cur.executemany(
        "INSERT OR IGNORE INTO devices (device_id, model) VALUES (?, ?)",
        [(f"V{i:05d}", f"EV-{i % 5}") for i in range(20_000)],
    )
    cur.execute("COMMIT")
    print("填充后总行数:", cur.execute("SELECT COUNT(*) FROM devices").fetchone()[0])

    # 3. 按 device_id 查询：UNIQUE 约束自带索引（sqlite_autoindex_*），天生走索引
    plan = cur.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM devices WHERE device_id = 'V00042'"
    ).fetchall()
    print("device_id 查询计划（UNIQUE 自带索引）:", plan)

    # 4. 按 model 查询（非唯一列）：无索引全表扫描 → 建索引后 SEARCH
    def measure_model() -> tuple[list[tuple], float]:
        plan = cur.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM devices WHERE model = 'EV-2'"
        ).fetchall()
        t0 = time.perf_counter()
        cur.execute("SELECT * FROM devices WHERE model = 'EV-2'").fetchall()
        return plan, (time.perf_counter() - t0) * 1000

    plan_before, ms_before = measure_model()
    print("model 查询（无索引）:", plan_before, f"{ms_before:.2f} ms")

    cur.execute("BEGIN")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_model ON devices(model)")
    cur.execute("COMMIT")
    plan_after, ms_after = measure_model()
    print("model 查询（有索引）:", plan_after, f"{ms_after:.2f} ms")

    row = cur.execute("SELECT * FROM devices WHERE device_id = 'V00042'").fetchone()
    print("按 device_id 查询结果:", row)
    conn.close()


if __name__ == "__main__":
    main()
