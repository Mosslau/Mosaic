# examples/ex01-sqlite-crud.py —— 用户 CRUD：标准库 sqlite3 建表 + 增删改查 + 参数化查询
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex01-sqlite-crud.py（离线可跑，已验证；数据库写入系统临时目录）
# 说明：对应主文档 3.1/3.2 与 roadmap「示例」。四个函数 create/get/update/delete 即完整 CRUD
#       服务，可被 ph10 的 FastAPI 路由直接调用。
import sqlite3
import tempfile
from pathlib import Path

DB_PATH = Path(tempfile.mkdtemp(prefix="ph11-ex01-")) / "app.db"


def create_user(conn: sqlite3.Connection, name: str, email: str) -> int:
    """插入用户，返回新行主键。值永远走 ? 占位符——参数化查询是防 SQL 注入的铁律。"""
    cur = conn.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
    )
    return cur.lastrowid  # 刚插入行的主键


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def update_user(conn: sqlite3.Connection, user_id: int, name: str) -> int:
    """改名并返回受影响行数（0 = 用户不存在）。"""
    cur = conn.execute(
        "UPDATE users SET name = ? WHERE id = ?", (name, user_id)
    )
    return cur.rowcount


def delete_user(conn: sqlite3.Connection, user_id: int) -> int:
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cur.rowcount


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 行支持按列名访问（像 dict 一样）
    conn.execute(
        """CREATE TABLE users (
               id INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               email TEXT UNIQUE
           )"""
    )

    # 1. 创建 + 读取
    uid = create_user(conn, "Alice", "alice@example.com")
    conn.commit()  # commit() 才落盘——忘 commit = 数据丢失
    print("create_user -> id:", uid)
    row = get_user(conn, uid)
    print("get_user    ->", dict(row) if row else None)

    # 2. 批量插入（executemany）+ 唯一约束冲突
    conn.executemany(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        [("Bob", "bob@example.com"), ("Carol", "carol@example.com")],
    )
    conn.commit()
    print("executemany -> 总行数:",
          conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    try:  # 重复 email 触发 UNIQUE 约束
        create_user(conn, "Dup", "alice@example.com")
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()  # 冲突后事务要回滚，否则后续操作都在坏事务里
        print("IntegrityError ->", e)

    # 3. 更新 + 删除
    n = update_user(conn, uid, "Alice2")
    conn.commit()
    print("update_user -> rowcount:", n, "新名字:",
          get_user(conn, uid)["name"] if get_user(conn, uid) else None)
    n = delete_user(conn, uid)
    conn.commit()
    print("delete_user -> rowcount:", n, "剩余用户数:",
          conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    conn.close()
    print("数据库文件:", DB_PATH)


if __name__ == "__main__":
    main()
