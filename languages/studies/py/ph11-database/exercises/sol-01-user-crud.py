# exercises/sol-01-user-crud.py —— 练习 1 参考实现：用户 CRUD（标准库 sqlite3）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 sol-01-user-crud.py（离线可跑，已验证；数据库写入系统临时目录）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 实际运行）：
#   create_user -> id: 1
#   注入尝试 -> 命中行数: 0 （0 = 没被注入）
#   重复 email -> UNIQUE constraint failed: users.email
#   update_user -> rowcount: 1 新名字: Alice2
#   delete_user -> rowcount: 1 剩余用户数: 0
import sqlite3
import tempfile
from pathlib import Path


def create_user(conn: sqlite3.Connection, name: str, email: str) -> int:
    """插入用户，返回新行主键。值永远走 ? 占位符——防 SQL 注入的铁律。"""
    return conn.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
    ).lastrowid


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def update_user(conn: sqlite3.Connection, user_id: int, name: str) -> int:
    """改名并返回受影响行数（0 = 用户不存在）。"""
    return conn.execute(
        "UPDATE users SET name = ? WHERE id = ?", (name, user_id)
    ).rowcount


def delete_user(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "DELETE FROM users WHERE id = ?", (user_id,)
    ).rowcount


def main() -> None:
    conn = sqlite3.connect(Path(tempfile.mkdtemp(prefix="ph11-sol01-")) / "app.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE users (
               id INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               email TEXT UNIQUE
           )"""
    )

    uid = create_user(conn, "Alice", "alice@example.com")
    conn.commit()
    print("create_user -> id:", uid)

    # 参数化查询防注入：把恶意输入当「值」而不是「SQL」
    evil = "' OR '1'='1"
    rows = conn.execute(
        "SELECT * FROM users WHERE name = ?", (evil,)
    ).fetchall()
    print("注入尝试 -> 命中行数:", len(rows), "（0 = 没被注入）")

    try:  # 重复 email 触发唯一约束
        create_user(conn, "Dup", "alice@example.com")
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print("重复 email ->", e)

    print("update_user -> rowcount:",
          update_user(conn, uid, "Alice2"), "新名字:",
          get_user(conn, uid)["name"] if get_user(conn, uid) else None)
    conn.commit()
    print("delete_user -> rowcount:",
          delete_user(conn, uid), "剩余用户数:",
          conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
