# 05 · 上下文管理器演示
# 运行：python3 demos/05_context_managers.py
import time
from contextlib import contextmanager


class Timer:
    """自定义上下文管理器：进入计时，退出打印耗时。"""

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 无论正常退出还是异常，这里都会执行
        print(f"耗时: {time.time() - self.start:.6f}s (异常: {exc_type is not None})")
        return False  # False = 不吞异常


@contextmanager
def log_block(name):
    """用生成器写上下文管理器：yield 前 = 进入，yield 后 = 退出。"""
    print(f"[进入] {name}")
    try:
        yield
    finally:
        print(f"[退出] {name}")


def main():
    print("== with：文件自动关闭 ==")
    with open("/dev/null", "w") as f:
        f.write("x")
    print("文件已自动关闭（无需手动 close）")

    print("\n== 自定义 Timer ==")
    with Timer():
        sum(range(1_000_000))

    print("\n== 异常时清理依然执行 ==")
    try:
        with log_block("危险操作"):
            raise ValueError("出错了")
    except ValueError:
        print("捕获异常——但 [退出] 已经打印过了")

    print("\n== 资源管理是'协议'不是'纪律' ==")


if __name__ == "__main__":
    main()
