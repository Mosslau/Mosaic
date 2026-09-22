# examples/ex01-mutable-default.py —— 可变默认参数：从错误写法到正确写法
# 验证环境：Python 3.13.12
# 运行：python3 ex01-mutable-default.py
# 已验证：本环境运行输出与注释中期望值一致

# 错误：每次不传 target 都共享同一个 list
def bad_append(item, target=[]):
    target.append(item)
    return target

# 正确：None 哨兵 + 函数体内创建
def good_append(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target

print("错误:", bad_append(1), bad_append(2), bad_append(3))
# 错误: [1, 2, 3] [1, 2, 3] [1, 2, 3] —— 三次打印看到的是同一个对象

print("正确:", good_append(1), good_append(2), good_append(3))
# 正确: [1] [2] [3] —— 每次都是独立的新 list
