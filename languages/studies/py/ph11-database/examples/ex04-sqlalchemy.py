# examples/ex04-sqlalchemy.py —— SQLAlchemy 2.0 Core 与 ORM：SQL 优先，ORM 只做映射层
# 验证环境：Python 3.13.9，sqlalchemy 2.0.43（已验证）
# 运行：python3 ex04-sqlalchemy.py（离线可跑，已验证；数据库写入系统临时目录）
# 说明：对应主文档 3.3/3.6。Core 的 text() 贴近 SQL，ORM 的 Mapped 风格是对象 ↔ 行映射；
#       echo=True 能看到 ORM 生成的 SQL——排查 N+1、看走没走索引的第一步。
import tempfile
from pathlib import Path

from sqlalchemy import QueuePool, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_PATH = Path(tempfile.mkdtemp(prefix="ph11-ex04-")) / "app.db"
URL = f"sqlite:///{DB_PATH}"


# ---------- 1. Core：SQL 表达式 + 连接管理（贴近 SQL） ----------
def core_demo() -> None:
    engine = create_engine(URL)
    with engine.begin() as conn:  # begin() 自动提交事务
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, city TEXT)"))
        conn.execute(
            text("INSERT INTO users (name, city) VALUES (:n, :c)"),
            [{"n": "Alice", "c": "Beijing"}, {"n": "Bob", "c": "Shanghai"}],
        )
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM users WHERE city = :c"), {"c": "Beijing"}
        ).fetchall()
        print("Core text() 查询 ->", rows)


# ---------- 2. ORM：Mapped 类型化模型 + Session（工作单元） ----------
class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(unique=True, index=True)
    model: Mapped[str]
    online: Mapped[bool] = mapped_column(default=False)


def orm_demo() -> None:
    engine = create_engine(URL, echo=True)  # echo=True：打印每条 ORM 生成的 SQL
    Base.metadata.create_all(engine)
    with Session(engine) as session:  # with 结束自动 close——防连接泄漏
        session.add(Device(device_id="V001", model="EV-A", online=True))
        session.commit()  # 忘记 commit = 数据没写进去
        stmt = select(Device).where(Device.device_id == "V001")
        device = session.scalars(stmt).one()
        print("ORM 查询结果 ->", device.device_id, device.model, device.online)
    print("（上面两条 SQL 就是 ORM 生成的——会读 SQL 才能调好 ORM）")


# ---------- 3. 连接池：pool_size/max_overflow/pool_pre_ping 与池状态 ----------
def pool_demo() -> None:
    engine = create_engine(
        URL,
        poolclass=QueuePool,  # SQLite 文件默认 NullPool；这里显式指定以展示池参数
        pool_size=2,          # 池内常驻连接数
        max_overflow=1,       # 高峰期最多再开 1 条
        pool_pre_ping=True,   # 借出前 ping 验证连接存活
    )
    print("初始池状态:", engine.pool.status())
    with engine.connect() as conn:  # 借出一条
        print("借出 1 条后:", engine.pool.status())
        conn.execute(text("SELECT 1"))
    print("归还后:", engine.pool.status())  # 归还回池，可复用


def main() -> None:
    core_demo()
    print()
    orm_demo()
    print()
    pool_demo()
    print("数据库文件:", DB_PATH)


if __name__ == "__main__":
    main()
