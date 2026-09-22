# examples/ex01-class-var.py —— 类变量共享陷阱：通过实例赋值会创建同名实例变量遮蔽类变量
# 来源：04-oop.md 第 6 章示例 1
# 验证环境：Python 3.13.12
# 运行：python3 ex01-class-var.py
# 验证状态：已验证

"""类变量共享陷阱演示：正确用 ClassName.count 修改，错误用 self.count 遮蔽。"""


class Counter:
    """计数器：用类变量统计实例数量。"""

    count = 0  # 类变量：所有实例共享

    def __init__(self, name):
        self.name = name
        Counter.count += 1  # 正确：通过类名修改类变量

    def bad_inc(self):
        self.count += 1  # 陷阱：创建同名实例变量，遮蔽类变量


def main():
    """演示类变量被实例变量遮蔽前后的计数差异。"""
    c1 = Counter("a")
    c2 = Counter("b")
    print(f"类:{Counter.count} c1:{c1.count} c2:{c2.count}")  # 类:2 c1:2 c2:2
    c1.bad_inc()
    c1.bad_inc()
    c2.bad_inc()
    print(f"类:{Counter.count} c1:{c1.count} c2:{c2.count}")  # 类:2 c1:4 c2:3


if __name__ == "__main__":
    main()
