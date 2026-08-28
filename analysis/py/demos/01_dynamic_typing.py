# 01 · 动态类型与鸭子类型演示
# 运行：python3 demos/01_dynamic_typing.py


def double(x):
    """同一个函数，四种类型，四种行为——运行时才检查类型。"""
    return x * 2


class Duck:
    def quack(self):
        return "quack!"


class Dog:
    def quack(self):
        return "woof... I mean quack?"


def make_sound(animal):
    """鸭子类型：不检查类型，只检查'你支持 quack 吗'。"""
    return animal.quack()


def main():
    print("== 动态类型：一个函数处理多种类型 ==")
    print(double(21))       # int
    print(double(2.5))      # float
    print(double("ab"))     # str：* 被重载为重复
    print(double([1, 2]))   # list：* 被重载为重复

    print("\n== 鸭子类型：不查类型，查行为 ==")
    print(make_sound(Duck()))
    print(make_sound(Dog()))  # Dog 没有 quack 就炸，有就过

    print("\n== 运行时才炸 ==")
    try:
        double(None)  # None * 2 → TypeError，运行时才暴露
    except TypeError as e:
        print(f"TypeError: {e} —— 编译期无从知道")


if __name__ == "__main__":
    main()
