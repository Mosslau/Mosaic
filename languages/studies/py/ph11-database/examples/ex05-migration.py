# examples/ex05-migration.py —— 手写迁移脚本：schema_version 让结构变更可追踪
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex05-migration.py（离线可跑，已验证；数据库写入系统临时目录）
# 说明：对应主文档 3.7（迁移）。alembic 在本环境未安装（python3 -c "import alembic" 失败），
#       这里用手写 schema_version 演示同一套思想：每个版本一段 SQL、按顺序执行、
#       已执行版本记录在表里、幂等可重放；失败在事务里整体回滚。装好 alembic 后，
#       这套逻辑由 `alembic revision --autogenerate` + `alembic upgrade head` 接管。
import sqlite3
import tempfile
from pathlib import Path

DB_PATH = Path(tempfile.mkdtemp(prefix="ph11-ex05-")) / "migrate.db"

MIGRATIONS: list[tuple[int, str]] = [  # 版本号递增，只增不改
    (1, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"),
    (2, "ALTER TABLE users ADD COLUMN email TEXT"),
    (3, "CREATE INDEX idx_users_name ON users(name)"),
    (4, "ALTER TABLE users ADD COLUMN city TEXT"),
]


def current_version(cur: sqlite3.Cursor) -> int:
    return cur.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ).fetchone()[0]


def migrate(conn: sqlite3.Connection, migrations: list[tuple[int, str]]) -> None:
    conn.isolation_level = None  # 手动事务：每个版本一个事务
    cur = conn.cursor()
    for version, sql in migrations:
        if version <= current_version(cur):
            continue
        print(f"应用迁移 v{version}: {sql}")
        cur.execute("BEGIN")
        try:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )
            cur.execute("COMMIT")
        except Exception as e:
            cur.execute("ROLLBACK")  # 迁移失败整体回滚，不留半成品结构
            raise RuntimeError(f"迁移 v{version} 失败: {e}") from e


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_version (
               version INTEGER PRIMARY KEY, applied_at TEXT
           )"""
    )

    print("首次迁移:")
    migrate(conn, MIGRATIONS)
    print("当前 schema 版本:", current_version(conn.cursor()))

    print("再次执行（应跳过全部）:")
    migrate(conn, MIGRATIONS)
    print("再次执行后版本仍为:", current_version(conn.cursor()))

    # v2 加的 email 列已真实存在：插入含 email 的行验证结构
    conn.execute("INSERT INTO users (name, email, city) VALUES (?, ?, ?)",
                 ("Alice", "alice@example.com", "Beijing"))
    conn.commit()
    print("插入含 v2/v4 列的数据 ->",
          conn.execute("SELECT name, email, city FROM users").fetchone())

    conn.close()
    print("数据库文件:", DB_PATH)


if __name__ == "__main__":
    main()
