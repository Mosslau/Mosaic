# 04 · 生成器与迭代器演示
# 运行：python3 demos/04_generators.py


def fib():
    """无限斐波那契生成器：惰性，一次只生产一个，内存 O(1)。"""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def take(n, gen):
    """取生成器前 n 项（惰性管道）。"""
    for _ in range(n):
        yield next(gen)


def main():
    print("== 无限序列：只取前 10 项 ==")
    for i, x in enumerate(take(10, fib())):
        print(f"fib({i}) = {x}")

    print("\n== 惰性 vs 一次性：内存对比 ==")
    import sys

    big_list = list(range(1_000_000))          # 一次性：100 万元素全部在内存
    gen = (x * 2 for x in range(1_000_000))    # 生成器表达式：惰性，几乎不占内存

    print(f"list 占内存: {sys.getsizeof(big_list) / 1024 / 1024:.1f} MB")
    print(f"生成器占内存: {sys.getsizeof(gen)} 字节（还没算任何元素）")
    print(f"但两者都能遍历：list[0]={big_list[0]}，生成器第一个={next(gen)}")

    print("\n== 生成器 = 协程雏形：yield 双向通信 ==")
    def echo():
        while True:
            received = yield
            print(f"收到: {received}")

    e = echo()
    next(e)          # 启动到第一个 yield
    e.send("hello")  # 往 yield 处发送值
    e.send("tenet")


if __name__ == "__main__":
    main()
