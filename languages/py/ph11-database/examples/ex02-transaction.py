# examples/ex02-transaction.py —— 事务与失败回滚：转账保证一致性边界（ACID）
# 验证环境：Python 3.13.9（stdlib，无第三方依赖）
# 运行：python3 ex02-transaction.py（离线可跑，已验证；数据库写入系统临时目录）
# 说明：对应主文档 3.4/4.2。手动事务用 isolation_level = None + 显式 BEGIN/COMMIT/ROLLBACK；
#       两条 UPDATE 要么都生效、要么都不生效——这就是「事务保证一致性边界」。
import sqlite3
import tempfile
from pathlib import Path

DB_PATH = Path(tempfile.mkdtemp(prefix="ph11-ex02-")) / "bank.db"


def transfer(cur: sqlite3.Cursor, frm: str, to: str, amount: float) -> None:
    """从 frm 转账 amount 给 to；余额不足则整笔回滚，两边余额都不变。"""
    cur.execute("BEGIN")  # 显式开启事务
    try:
        bal = cur.execute(
            "SELECT balance FROM accounts WHERE name = ?", (frm,)
        ).fetchone()[0]
        if bal < amount:
            raise ValueError(f"{frm} 余额不足: {bal}")
        cur.execute(
            "UPDATE accounts SET balance = balance - ? WHERE name = ?",
            (amount, frm),
        )
        cur.execute(
            "UPDATE accounts SET balance = balance + ? WHERE name = ?",
            (amount, to),
        )
        cur.execute("COMMIT")  # 全部成功 → 落盘
        print(f"转账成功: {frm} -> {to} {amount}")
    except Exception as e:
        cur.execute("ROLLBACK")  # 任一步失败 → 全部撤销
        print(f"转账失败已回滚: {e}")


def balances(cur: sqlite3.Cursor) -> list[tuple[str, float]]:
    return cur.execute(
        "SELECT name, balance FROM accounts ORDER BY id"
    ).fetchall()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None  # 关闭隐式事务：BEGIN/COMMIT/ROLLBACK 全手动
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE accounts (
               id INTEGER PRIMARY KEY, name TEXT, balance REAL
           )"""
    )
    cur.execute("INSERT INTO accounts (name, balance) VALUES ('A', 1000)")
    cur.execute("INSERT INTO accounts (name, balance) VALUES ('B', 0)")

    print("初始余额:", balances(cur))
    transfer(cur, "A", "B", 2000)  # 失败：余额不足 → 整笔回滚
    print("失败后余额:", balances(cur))
    transfer(cur, "A", "B", 300)  # 成功
    print("成功后余额:", balances(cur))  # A=700, B=300（第一次的 2000 没生效）

    # 第二次转账用 savepoint 演示：嵌套回滚只撤销 savepoint 之后的操作
    cur.execute("BEGIN")
    cur.execute("SAVEPOINT sp1")
    cur.execute("UPDATE accounts SET balance = balance + 100 WHERE name = 'B'")
    cur.execute("ROLLBACK TO sp1")  # 只回滚到 savepoint，BEGIN 还开着
    cur.execute("COMMIT")
    print("savepoint 回滚后余额:", balances(cur))

    conn.close()
    print("数据库文件:", DB_PATH)


if __name__ == "__main__":
    main()
