# 02 · 数据模型（魔术方法）演示
# 运行：python3 demos/02_data_model.py


class Vector2D:
    """实现魔术方法后，这个类无缝融入 Python 语法。"""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):          # a + b
        return Vector2D(self.x + other.x, self.y + other.y)

    def __mul__(self, k):              # a * k
        return Vector2D(self.x * k, self.y * k)

    def __len__(self):                 # len(a) —— 元素个数
        return 2

    def __repr__(self):                # repr(a) / 调试打印
        return f"Vector2D({self.x}, {self.y})"

    def __eq__(self, other):           # a == b
        return isinstance(other, Vector2D) and self.x == other.x and self.y == other.y


def main():
    a = Vector2D(1, 2)
    b = Vector2D(3, 4)

    print("== 运算符 ==")
    print("a + b =", a + b)            # 走 __add__
    print("a * 3 =", a * 3)            # 走 __mul__

    print("\n== 内置函数 ==")
    print("len(a) =", len(a))          # 走 __len__
    print("repr(a) =", repr(a))        # 走 __repr__

    print("\n== 比较 ==")
    print("a == Vector2D(1, 2):", a == Vector2D(1, 2))   # 走 __eq__
    print("a == b:", a == b)

    print("\n== 关键：语言语法 = 协议，自定义类型是一等公民 ==")


if __name__ == "__main__":
    main()
