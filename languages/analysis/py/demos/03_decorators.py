# 03 · 装饰器与闭包演示
# 运行：python3 demos/03_decorators.py
import time


def make_counter():
    """闭包：外层函数的 count 被内层函数捕获，外层结束后依然活着。"""
    count = 0

    def inc():
        nonlocal count
        count += 1
        return count

    return inc


def timing(fn):
    """装饰器：包装函数，附加计时行为（横切逻辑，不改业务代码）。"""

    def wrapper(*args, **kwargs):
        start = time.time()
        result = fn(*args, **kwargs)
        print(f"{fn.__name__} 耗时 {time.time() - start:.6f}s")
        return result

    return wrapper


@timing  # 语法糖：等价于 slow_fib = timing(slow_fib)
def slow_fib(n):
    if n < 2:
        return n
    return slow_fib(n - 1) + slow_fib(n - 2)


def main():
    print("== 闭包：计数器 ==")
    c = make_counter()
    print(c(), c(), c())  # 1 2 3 —— count 存活在闭包里

    print("\n== 装饰器：@timing ==")
    print("fib(20) =", slow_fib(20))  # 打印耗时 + 结果

    print("\n== 等价写法（语法糖真相）==")
    def plain_add(a, b):
        return a + b

    wrapped = timing(plain_add)  # 手动应用装饰器
    print("wrapped(1, 2) =", wrapped(1, 2))


if __name__ == "__main__":
    main()
