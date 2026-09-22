# project/tests/test_device_manager.py —— 离线测试：迁移 / CRUD / 唯一约束 / 批量入库 / 统计 / 缓存
# 运行（在 project/ 目录下）：pytest -q（已验证，13 个用例全过，不依赖网络与第三方库）
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 导入平级的 device_manager.py

from device_manager import (  # noqa: E402
    Database,
    DeviceRepo,
    DeviceService,
    StatusRepo,
    TTLCache,
    UserRepo,
    demo,
    main,
    migrate,
)


def make_db(tmp_path) -> Database:
    """每个用例一个独立临时 sqlite 库，互不污染。"""
    return Database(tmp_path / "test.db")


# ---------- 迁移 ----------
def test_migration_idempotent(tmp_path):
    db = make_db(tmp_path)
    cur = db.conn.cursor()
    assert cur.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 4
    migrate(db.conn)  # 再跑一遍：应跳过全部
    assert cur.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 4
    db.conn.close()


def test_migration_creates_all_tables(tmp_path):
    db = make_db(tmp_path)
    tables = {
        r[0] for r in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "devices", "device_status", "schema_version"} <= tables
    db.conn.close()


# ---------- 用户 CRUD ----------
def test_user_crud(tmp_path):
    db = make_db(tmp_path)
    users = UserRepo(db)
    uid = users.create("Alice", "alice@example.com")
    assert uid == 1
    assert users.get(uid)["name"] == "Alice"
    assert users.update(uid, "Alice2") == 1
    assert users.get(uid)["name"] == "Alice2"
    assert users.delete(uid) == 1
    assert users.get(uid) is None
    db.conn.close()


def test_user_unique_email(tmp_path):
    db = make_db(tmp_path)
    users = UserRepo(db)
    users.create("Alice", "alice@example.com")
    try:
        users.create("Dup", "alice@example.com")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("重复 email 应抛 IntegrityError")
    assert db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    db.conn.close()


# ---------- 设备注册（vin 唯一） ----------
def test_device_register_duplicate_vin(tmp_path):
    db = make_db(tmp_path)
    devices = DeviceRepo(db)
    devices.register("V001", "EV-A")
    try:
        devices.register("V001", "EV-A")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("重复 vin 应抛 IntegrityError")
    assert len(devices.list_all()) == 1
    db.conn.close()


def test_device_set_online(tmp_path):
    db = make_db(tmp_path)
    devices = DeviceRepo(db)
    devices.register("V001", "EV-A")
    assert devices.set_online("V001", True) == 1
    assert devices.get_by_vin("V001")["online"] == 1
    db.conn.close()


# ---------- 状态批量入库 / 查询 / 统计 ----------
def _seed_status(db: Database) -> None:
    """3 台设备各 4 条：V001 speed 50/60/70/80 → avg 65 max 80；V002 90/100 → avg 95 max 100。"""
    status = StatusRepo(db)
    status.ingest_batch([
        (1, "2024-06-01T08:00:00", "online", 50.0),
        (1, "2024-06-01T08:10:00", "online", 60.0),
        (1, "2024-06-01T08:20:00", "online", 70.0),
        (1, "2024-06-01T08:30:00", "online", 80.0),
        (2, "2024-06-01T08:00:00", "online", 90.0),
        (2, "2024-06-01T08:10:00", "online", 100.0),
    ])


def test_status_batch_ingest_count(tmp_path):
    db = make_db(tmp_path)
    status = StatusRepo(db)
    assert status.ingest_batch([
        (1, "2024-06-01T08:00:00", "online", 50.0),
        (2, "2024-06-01T08:00:00", "online", 60.0),
    ]) == 2
    assert db.conn.execute("SELECT COUNT(*) FROM device_status").fetchone()[0] == 2
    db.conn.close()


def test_status_query_window(tmp_path):
    db = make_db(tmp_path)
    _seed_status(db)
    status = StatusRepo(db)
    all_rows = status.query(1, limit=10)
    assert len(all_rows) == 4
    window = status.query(1, since="2024-06-01T08:10:00", until="2024-06-01T08:20:00")
    assert [r["speed"] for r in window] == [60.0, 70.0]
    limited = status.query(1, limit=2)
    assert len(limited) == 2
    db.conn.close()


def test_status_stats(tmp_path):
    db = make_db(tmp_path)
    _seed_status(db)
    status = StatusRepo(db)
    assert status.stats() == [
        {"device_id": 1, "count": 4, "avg_speed": 65.0, "max_speed": 80.0},
        {"device_id": 2, "count": 2, "avg_speed": 95.0, "max_speed": 100.0},
    ]
    assert status.stats(device_id=2) == [
        {"device_id": 2, "count": 2, "avg_speed": 95.0, "max_speed": 100.0},
    ]
    assert status.stats(device_id=999) == []
    db.conn.close()


# ---------- 缓存（TTL 过期 + 主动失效） ----------
def test_cache_hit_miss_and_ttl(tmp_path):
    db = make_db(tmp_path)
    cache = TTLCache(ttl=0.2)
    service = DeviceService(db, cache)
    service.devices.register("V001", "EV-A")

    r1 = service.get_device("V001")
    assert r1["cached"] is False          # miss：查库回填
    r2 = service.get_device("V001")
    assert r2["cached"] is True           # hit
    assert cache.hits == 1 and cache.misses == 1

    time.sleep(0.3)                       # 超过 TTL
    r3 = service.get_device("V001")
    assert r3["cached"] is False          # 过期后重新 miss
    assert cache.misses == 2
    db.conn.close()


def test_cache_invalidation_on_update(tmp_path):
    db = make_db(tmp_path)
    cache = TTLCache(ttl=60)
    service = DeviceService(db, cache)
    service.devices.register("V001", "EV-A")

    service.get_device("V001")            # miss + 回填
    assert service.update_device("V001", online=False) == 1  # 写库删缓存
    r = service.get_device("V001")        # 缓存已删 → miss
    assert r["cached"] is False
    db.conn.close()


# ---------- CLI 演示 ----------
def test_demo_offline(capsys):
    assert demo() == 0
    out = capsys.readouterr().out
    for fragment in ("迁移完成", "用户 CRUD", "重复 vin 被拒", "状态批量入库",
                     "分组统计", "缓存", "自检通过"):
        assert fragment in out


def test_main_demo_flag():
    assert main(["--demo"]) == 0
