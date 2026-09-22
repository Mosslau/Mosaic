#!/usr/bin/env python3
# examples/ex01-threading-io.py —— threading：线程基础、IO 密集实测与线程安全（主文档 3.1/3.2）
# 验证环境：Python 3.13.9（macOS arm64，14 核，标准库，零第三方依赖）
# 运行：python3 ex01-threading-io.py（离线可跑，已验证）
# 验证状态：已验证 —— 输出顺序不定（如实标注）；本机实测耗时：串行 ≈ 1.07s，线程池(8) ≈ 0.16s；
#           竞争条件无锁版 ~500/4000（丢 ~3500），加锁版恒为 4000（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 1.087s / 线程池 0.163s（一次运行）；无锁 501/4000、加锁 4000/4000
import threading
import time
from concurrent.futures import ThreadPoolExecutor


# ---- 3.1 线程基础：Thread + start/join，输出顺序不定 ----
def shout(name: str) -> None:
    """模拟一个会「插队」的任务：睡一小会儿让出 CPU，放大顺序不确定性。"""
    time.sleep(0.001)
    print(f"{name} 完成")


def part_a_thread_basics() -> None:
    """直接创建线程：start 只是『排上队』，执行顺序由操作系统调度决定，每次运行都可能不同。"""
    print("== A. 线程直接创建：运行两次输出顺序可能不同 ==")
    for _ in range(2):
        threads = [threading.Thread(target=shout, args=(f"T{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()  # join：等该线程跑完再继续主流程
        print("--- 一轮结束 ---")


# ---- 3.1 IO 密集实测：串行 vs 线程池 ----
N_TASKS = 20
IO_WAIT = 0.05  # 每次「IO 等待」时长（模拟网络/磁盘，等待时线程会释放 GIL）


def io_task(i: int) -> int:
    """模拟 IO 密集任务：绝大部分时间在等待，等待期间释放 GIL。"""
    time.sleep(IO_WAIT)
    return i * 2


def part_b_io_bound() -> None:
    print("== B. IO 密集实测：串行 vs 线程池(8)，20 个任务 × 0.05s ==")
    t0 = time.perf_counter()
    serial = [io_task(i) for i in range(N_TASKS)]
    t_serial = time.perf_counter() - t0
    print(f"串行: {t_serial:.3f}s")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        pooled = list(ex.map(io_task, range(N_TASKS)))
    t_pool = time.perf_counter() - t0
    print(f"线程池(8): {t_pool:.3f}s（≈ {t_serial / t_pool:.1f} 倍加速）")

    # 计数正确性：两种方式结果必须完全一致
    assert serial == pooled, "线程池结果与串行不一致！"
    print(f"结果校验: 20 个任务全部拿到（{serial[0]}, ..., {serial[-1]}）")


# ---- 3.2 线程安全：无锁竞争 vs 加锁 ----
N_THREADS = 8
LOOP_ITERS = 500


def race_unlocked() -> int:
    """无锁版：每个线程循环做『读 → 让出 → 写』，读与写之间被插队就会丢计数。"""
    counter: dict[str, int] = {"n": 0}

    def incr() -> None:
        for _ in range(LOOP_ITERS):
            v = counter["n"]  # 读
            time.sleep(0.000001)  # 让出 CPU，制造切换窗口
            counter["n"] = v + 1  # 写（若期间别人写过，这里会覆盖 → 丢计数）

    threads = [threading.Thread(target=incr) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return counter["n"]


def race_locked() -> int:
    """加锁版：Lock 把『读-写』包成临界区，同一时刻只有一个线程能进。"""
    counter: dict[str, int] = {"n": 0}
    lock = threading.Lock()

    def incr() -> None:
        for _ in range(LOOP_ITERS):
            with lock:  # 进入临界区（阻塞等待其他线程释放）
                v = counter["n"]
                time.sleep(0.000001)
                counter["n"] = v + 1

    threads = [threading.Thread(target=incr) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return counter["n"]


def part_c_race() -> None:
    expected = N_THREADS * LOOP_ITERS
    print(f"== C. 竞争条件实测：8 线程 × {LOOP_ITERS} 次『读-写』，期望 {expected} ==")
    got = race_unlocked()
    print(f"无锁: {got}（丢了 {expected - got} 次）")
    got_locked = race_locked()
    print(f"加锁: {got_locked}（分毫不差）")


if __name__ == "__main__":
    part_a_thread_basics()
    part_b_io_bound()
    part_c_race()
