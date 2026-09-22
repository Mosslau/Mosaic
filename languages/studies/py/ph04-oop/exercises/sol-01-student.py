# exercises/sol-01-student.py —— 学生类：平均分 + __lt__ 排序（参考实现）
# 来源：exercises/README.md 练习 1
# 验证环境：Python 3.13.12
# 运行：python3 sol-01-student.py
# 验证状态：已验证

"""学生类：成绩管理、平均分计算、按平均分排序、同名相等。"""


class Student:
    """学生：姓名 + 可变成绩列表。"""

    def __init__(self, name):
        self.name = name
        self.scores = []

    def add_score(self, score):
        """添加一条成绩（0~100 之间）。"""
        if not 0 <= score <= 100:
            raise ValueError(f"成绩需在 0~100 之间: {score}")
        self.scores.append(score)

    def average(self):
        """平均分；无成绩时返回 0.0。"""
        if not self.scores:
            return 0.0
        return sum(self.scores) / len(self.scores)

    def __lt__(self, other):
        """按平均分比较，供 sorted() 排序。"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.average() < other.average()

    def __eq__(self, other):
        """同名学生视为同一人。"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        """与 __eq__ 配对：同名可哈希。"""
        return hash(self.name)

    def __str__(self):
        return f"Student({self.name}, 平均分={self.average():.1f})"

    def __repr__(self):
        return f"Student({self.name!r})"


def main():
    """演示平均分、排序与同名去重。"""
    xiaoming = Student("小明")
    xiaoming.add_score(80)
    xiaoming.add_score(100)
    print(f"小明平均分: {xiaoming.average()}")  # 90.0

    xiaogang = Student("小刚")
    xiaogang.add_score(70)

    students = [xiaoming, xiaogang]
    for s in sorted(students):
        print(s)  # 按平均分升序：小刚在前

    another_ming = Student("小明")
    print(f"同名相等: {xiaoming == another_ming}")  # True
    print(f"set 去重后数量: {len({xiaoming, another_ming})}")  # 1


if __name__ == "__main__":
    main()
