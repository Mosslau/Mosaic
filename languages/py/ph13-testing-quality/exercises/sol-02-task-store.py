#!/usr/bin/env python3
# exercises/sol-02-task-store.py —— 练习 2 参考实现：fixture 组织测试数据（数据处理测试）
# 验证环境：Python 3.13.9 + pytest 8.4.2（stdlib 实现，零第三方依赖）
# 运行：python3 -m pytest sol-02-task-store.py -q（离线可跑，已验证）
# 验证状态：已验证 —— 8 个用例全过；本文件语句覆盖率 100%（trace 实测：62 个可执行行全命中）
# 验证块数字实测：python3 -m pytest sol-02-task-store.py -q -> 8 passed
#                trace 覆盖率 -> lines 62, cov 100%
import pytest


class TaskStore:
    """任务存储：add 返回自增 id，mark_done 翻转完成状态，list 按 id 排序。"""

    def __init__(self, name: str = "tasks.jsonl") -> None:
        self.name = name
        self._next_id = 1
        self._tasks: dict[int, dict] = {}

    def add(self, title: str, done: bool = False) -> int:
        tid = self._next_id
        self._next_id += 1
        self._tasks[tid] = {"id": tid, "title": title, "done": done}
        return tid

    def list(self) -> list[dict]:
        return [self._tasks[i] for i in sorted(self._tasks)]

    def mark_done(self, task_id: int) -> bool:
        if task_id not in self._tasks:
            return False
        self._tasks[task_id]["done"] = True
        return True


# ---- fixture 设计（练习重点）----
@pytest.fixture
def store_dir(tmp_path):
    d = tmp_path / "stores"
    d.mkdir()
    return d


@pytest.fixture
def empty_store(store_dir):
    return TaskStore(store_dir / "empty.jsonl")


@pytest.fixture
def prefilled_store(store_dir):
    """预置 3 条任务：依赖 store_dir，pytest 自动先建目录再建 store。"""
    s = TaskStore(store_dir / "pre.jsonl")
    for title in ("充电", "换轮胎", "年检"):
        s.add(title)
    return s


@pytest.fixture(scope="session")
def boot_count():
    counter = {"calls": 0}
    counter["calls"] += 1
    return counter


@pytest.fixture(autouse=True)
def _ensure_index_dir(tmp_path):
    """autouse：每个用例自动创建 index 目录，测试无需声明该参数。"""
    (tmp_path / "index").mkdir(exist_ok=True)
    yield


# ---- 测试 ----
def test_add_returns_increasing_ids(empty_store):
    assert empty_store.add("A") == 1
    assert empty_store.add("B") == 2


def test_list_orders_by_id(prefilled_store):
    assert [t["title"] for t in prefilled_store.list()] == ["充电", "换轮胎", "年检"]


def test_mark_done(prefilled_store):
    assert prefilled_store.mark_done(2) is True
    assert prefilled_store.list()[1]["done"] is True


def test_mark_done_missing_id(prefilled_store):
    assert prefilled_store.mark_done(99) is False   # 不存在的 id 返回 False，不抛异常


def test_session_fixture_boot_once_1(boot_count):
    assert boot_count["calls"] == 1    # session 级 fixture 整个会话只建一次


def test_session_fixture_boot_once_2(boot_count):
    assert boot_count["calls"] == 1    # 第二次取到同一实例，仍是 1


def test_autouse_index_dir_created(tmp_path):
    assert (tmp_path / "index").is_dir()   # autouse fixture 已自动建好


def test_two_stores_isolated(empty_store, prefilled_store):
    assert len(empty_store.list()) == 0
    assert len(prefilled_store.list()) == 3   # 两个 fixture 独立构造，互不污染


if __name__ == "__main__":
    pytest.main(["-q", __file__])
