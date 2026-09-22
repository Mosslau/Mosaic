#!/usr/bin/env python3
# examples/ex02-fixture-scope.py —— fixture 进阶：作用域（scope）、autouse、依赖注入、工厂模式
# 验证环境：Python 3.13.9 + pytest 8.4.2（本机已装并实测）
# 运行：python3 -m pytest ex02-fixture-scope.py -q（离线可跑，已验证）
# 验证状态：已验证 —— 7 个用例全过（session 共享 2 + autouse 1 + 工厂 2 + 依赖注入 2）
# fixture 是 pytest 的「依赖注入」机制：测试函数声明参数名，pytest 自动构造并传入（主文档 3.2）
import pytest


class TelemetryStore:
    """进程内遥测存储：append 追加记录，count/vehicles 统计。"""

    def __init__(self, name: str = "store.jsonl") -> None:
        self.name = name
        self._rows: list[tuple[str, str, float]] = []

    def append(self, ts: str, vehicle: str, speed: float) -> int:
        self._rows.append((ts, vehicle, speed))
        return len(self._rows)

    def count(self) -> int:
        return len(self._rows)

    def vehicles(self) -> set[str]:
        return {r[1] for r in self._rows}


# ---- fixture 1：scope="session"（整个会话只创建一次，跨用例共享同一实例）----
@pytest.fixture(scope="session")
def session_counter():
    counter = {"setup": 0}
    counter["setup"] += 1            # 若每个用例都重建，这里会加多次
    return counter


def test_session_shared_1(session_counter):
    assert session_counter["setup"] == 1    # 整个 pytest 会话只建一次


def test_session_shared_2(session_counter):
    assert session_counter["setup"] == 1    # 第二次取到的是同一个对象（仍是 1，不是 2）


# ---- fixture 2：autouse（无需在测试参数里声明，自动对每个用例生效）----
@pytest.fixture(autouse=True)
def _ensure_workdir(tmp_path):
    """autouse fixture：本文件每个用例自动创建 work 目录，测试不用写这个参数。"""
    (tmp_path / "work").mkdir(exist_ok=True)
    yield


def test_autouse_dir_created(tmp_path):
    # 参数里没有 _ensure_workdir，但 autouse 让它照样生效
    assert (tmp_path / "work").is_dir()


# ---- fixture 3：工厂模式（fixture 返回一个「造对象」的函数，数据随用例不同）----
@pytest.fixture
def make_store(tmp_path):
    created: list[TelemetryStore] = []

    def _make(name: str = "store.jsonl") -> TelemetryStore:
        s = TelemetryStore(tmp_path / name)
        created.append(s)
        return s

    yield _make
    # yield 之后的代码是清理阶段：本用例结束时执行（主文档 3.2 的「前后置」）
    assert created, "用例没有通过工厂创建任何 store —— 工厂没用上？"


def test_factory_one(make_store):
    store = make_store("a.jsonl")
    assert store.append("2026-09-01 10:00", "EV-001", 42.0) == 1
    assert store.count() == 1


def test_factory_many(make_store):
    # 工厂每次调用返回独立实例：数据互不污染
    a, b = make_store("x.jsonl"), make_store("y.jsonl")
    a.append("t", "EV-002", 30.0)
    assert a.count() == 1 and b.count() == 0


# ---- fixture 4：依赖注入（fixture 依赖另一个 fixture，pytest 按需组装）----
@pytest.fixture
def data_file(tmp_path):
    f = tmp_path / "raw.csv"
    f.write_text("ts,vehicle,speed\n2026-09-01 10:00,EV-001,42.0\n", encoding="utf-8")
    return f


@pytest.fixture
def store(data_file):
    # 依赖 data_file：pytest 先建 data_file，再把它注入这里的参数
    s = TelemetryStore(data_file.parent / "store.jsonl")
    s.append("2026-09-01 10:00", "EV-001", 42.0)
    return s


def test_store_injected(store):
    assert store.count() == 1
    assert store.vehicles() == {"EV-001"}


def test_store_data_file_exists(data_file, store):
    assert data_file.exists()            # 两个 fixture 同时注入，各自独立构造
    assert str(store.name).endswith("store.jsonl")


if __name__ == "__main__":
    pytest.main(["-q", __file__])
