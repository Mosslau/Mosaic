# project/device_manager.py —— ph11 阶段项目：设备管理后端（数据层）
# 验证环境：Python 3.13.9（stdlib，零第三方依赖）
# 运行：python3 device_manager.py --demo（离线可跑，已验证；数据库与缓存全部走系统临时目录）
# 测试：pytest -q（tests/test_device_manager.py，已验证）
# 说明：对应 roadmap「推荐项目」第一个「设备管理后端」——devices 表（vin 唯一索引）+
#       device_status 状态表（复合索引）+ 用户 CRUD + 手写迁移脚本演进结构 +
#       缓存设备热点查询（TTL 过期 + 写库主动失效）。标准库实现，SQL 优先；
#       换 SQLAlchemy + Alembic 与 redis-py 的落法见 README「扩展方向」。
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# ---------- 迁移：schema_version 让结构变更可追踪（版本化、幂等、失败回滚） ----------
MIGRATIONS: list[tuple[int, str]] = [
    (1, "CREATE TABLE users ("
        "id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE)"),
    (2, "CREATE TABLE devices ("
        "id INTEGER PRIMARY KEY, vin TEXT NOT NULL UNIQUE, "
        "model TEXT NOT NULL, online INTEGER DEFAULT 0)"),
    (3, "CREATE TABLE device_status ("
        "id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, "
        "ts TEXT NOT NULL, status TEXT NOT NULL, speed REAL)"),
    (4, "CREATE INDEX idx_status_device_ts ON device_status(device_id, ts)"),
]


def migrate(conn: sqlite3.Connection) -> None:
    """按版本号顺序应用未执行的迁移；每个版本一个事务，失败整体回滚。"""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version ("
                 "version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.isolation_level = None
    cur = conn.cursor()

    def current_version() -> int:
        return cur.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        ).fetchone()[0]

    for version, sql in MIGRATIONS:
        if version <= current_version():
            continue
        cur.execute("BEGIN")
        try:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_version (version, applied_at) "
                "VALUES (?, datetime('now'))",
                (version,),
            )
            cur.execute("COMMIT")
        except Exception as e:
            cur.execute("ROLLBACK")
            raise RuntimeError(f"迁移 v{version} 失败: {e}") from e


# ---------- 数据库连接与仓库层（Repository） ----------
class Database:
    """一个连接 + 自动迁移；行按列名访问。"""

    def __init__(self, path: str | Path) -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)


class UserRepo:
    """用户 CRUD：值永远走 ? 占位符（参数化查询防注入）。"""

    def __init__(self, db: Database) -> None:
        self.conn = db.conn

    def create(self, name: str, email: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
        )
        self.conn.commit()
        return cur.lastrowid

    def get(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    def update(self, user_id: int, name: str) -> int:
        cur = self.conn.execute(
            "UPDATE users SET name = ? WHERE id = ?", (name, user_id)
        )
        self.conn.commit()
        return cur.rowcount

    def delete(self, user_id: int) -> int:
        cur = self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        return cur.rowcount


class DeviceRepo:
    """设备注册与查询：vin 唯一约束自带索引，重复注册抛 IntegrityError。"""

    def __init__(self, db: Database) -> None:
        self.conn = db.conn

    def register(self, vin: str, model: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO devices (vin, model) VALUES (?, ?)", (vin, model)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_by_vin(self, vin: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM devices WHERE vin = ?", (vin,)
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM devices ORDER BY id"
        ).fetchall()

    def set_online(self, vin: str, online: bool) -> int:
        cur = self.conn.execute(
            "UPDATE devices SET online = ? WHERE vin = ?", (int(online), vin)
        )
        self.conn.commit()
        return cur.rowcount


class StatusRepo:
    """车辆状态：高频批量写入 + 复合索引查询 + 分组统计。"""

    def __init__(self, db: Database) -> None:
        self.conn = db.conn

    def ingest_batch(self, rows: list[tuple[int, str, str, float]]) -> int:
        """批量写入状态行，返回写入条数。"""
        self.conn.executemany(
            "INSERT INTO device_status (device_id, ts, status, speed) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def query(self, device_id: int, since: str | None = None,
              until: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
        """按设备 + 可选时间窗口查询（走 idx_status_device_ts 复合索引）。"""
        sql = "SELECT * FROM device_status WHERE device_id = ?"
        params: list[Any] = [device_id]
        if since is not None:
            sql += " AND ts >= ?"
            params.append(since)
        if until is not None:
            sql += " AND ts <= ?"
            params.append(until)
        sql += " ORDER BY ts LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def stats(self, device_id: int | None = None) -> list[dict]:
        """按设备分组统计：count / avg_speed / max_speed；不传 device_id 统计全部。"""
        sql = ("SELECT device_id, COUNT(*) AS count, "
               "ROUND(AVG(speed), 1) AS avg_speed, MAX(speed) AS max_speed "
               "FROM device_status")
        params: list[Any] = []
        if device_id is not None:
            sql += " WHERE device_id = ?"
            params.append(device_id)
        sql += " GROUP BY device_id ORDER BY device_id"
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]


# ---------- 缓存：TTL 过期 + 主动失效（stdlib 版；redis 落法见 README 扩展方向） ----------
class TTLCache:
    """带过期时间的进程内缓存：get/set/delete + 命中统计。"""

    def __init__(self, ttl: float = 5.0) -> None:
        self.ttl = ttl
        self._store: dict[str, tuple[float, str]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            self.misses += 1
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:  # 惰性删除：访问时发现过期即删
            self._store.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value: str, ttl: float | None = None) -> None:
        self._store[key] = (time.monotonic() + (ttl or self.ttl), value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class DeviceService:
    """业务层：设备查询走缓存（缓存旁路），写库后主动删缓存防脏读。"""

    def __init__(self, db: Database, cache: TTLCache) -> None:
        self.db = db
        self.devices = DeviceRepo(db)
        self.status = StatusRepo(db)
        self.cache = cache

    def get_device(self, vin: str) -> dict:
        """查设备（热点查询走缓存）；未命中查库并回填。"""
        key = f"device:{vin}"
        cached = self.cache.get(key)
        if cached is not None:
            return {"vin": vin, "model": cached, "cached": True}
        row = self.devices.get_by_vin(vin)
        if row is None:
            raise KeyError(f"设备不存在: {vin}")
        self.cache.set(key, row["model"])
        return {"vin": vin, "model": row["model"], "cached": False}

    def update_device(self, vin: str, online: bool) -> int:
        """更新设备并删除缓存（主动失效）——下次读取必然重新查库。"""
        n = self.devices.set_online(vin, online)
        self.cache.delete(f"device:{vin}")
        return n


# ---------- CLI：--demo 离线全链路演示 ----------
def demo() -> int:
    """临时库跑通全链路：迁移 → 用户 CRUD → 设备注册 → 状态批量入库 → 查询/统计 → 缓存。"""
    tmp = Path(tempfile.mkdtemp(prefix="ph11-project-"))
    db = Database(tmp / "device.db")
    users = UserRepo(db)
    cache = TTLCache(ttl=1.0)
    service = DeviceService(db, cache)

    # 1. 迁移
    cur = db.conn.cursor()
    print("迁移完成 -> schema 版本:",
          cur.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],
          "（users / devices / device_status / 复合索引 共 4 步）")

    # 2. 用户 CRUD
    uid = users.create("Alice", "alice@example.com")
    print("用户 CRUD -> create id:", uid, "| update rowcount:",
          users.update(uid, "Alice2"), "| get:",
          dict(users.get(uid)))

    # 3. 设备注册（vin 唯一）
    for vin, model in [("V001", "EV-A"), ("V002", "EV-B"), ("V003", "EV-C")]:
        service.devices.register(vin, model)
    try:
        service.devices.register("V001", "EV-A")  # 重复 vin
    except sqlite3.IntegrityError as e:
        print("重复 vin 被拒 ->", e)

    # 4. 状态批量入库：3 台车 × 24 条 = 72 条（按 (device_id, ts) 复合索引）
    rows = [
        (i % 3 + 1, f"2024-06-01T08:{h:02d}:{m:02d}", "online",
         round(50 + (i % 24) * 0.5, 1))
        for i, (h, m) in enumerate(divmod(i, 60) for i in range(72))
    ]
    inserted = service.status.ingest_batch(rows)
    print(f"状态批量入库 -> {inserted} 条（3 车 × 24 条）")

    # 5. 查询 + 统计
    first = service.status.query(1, since="2024-06-01T08:00:00",
                                 until="2024-06-01T08:05:00", limit=3)
    print("按设备+时间窗口查询 ->", len(first), "条，首条 speed:",
          first[0]["speed"] if first else None)
    print("分组统计 ->", service.status.stats())

    # 6. 缓存：热点查询（miss → hit → 主动失效 → TTL 过期）
    service.get_device("V001")  # miss 1：查库回填
    service.get_device("V001")  # hit 1
    r3 = service.get_device("V001")  # hit 2
    print("缓存 -> hits:", cache.hits, "misses:", cache.misses,
          "| r3 cached:", r3["cached"])
    service.update_device("V001", online=False)  # 写库主动删缓存
    service.get_device("V001")  # miss 2：缓存已被删
    r5 = service.get_device("V001")  # hit 3
    print("写库主动失效后 -> misses:", cache.misses,
          "| r5 cached:", r5["cached"])
    time.sleep(1.2)  # 等 TTL 过期
    r6 = service.get_device("V001")  # miss 3：缓存已过期
    print("TTL 过期后 -> misses:", cache.misses, "| r6 cached:", r6["cached"])

    # 自检
    assert cur.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 3
    assert cur.execute("SELECT COUNT(*) FROM device_status").fetchone()[0] == 72
    assert cache.hits == 3 and cache.misses == 3  # 3 hit + 3 miss（初始/失效/过期）
    print("自检通过：3 台设备、72 条状态、缓存 hit/miss 计数正确")
    db.conn.close()
    return 0


def main(argv: list[str]) -> int:
    if "--demo" in argv:
        return demo()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
