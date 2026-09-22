# Python 数据结构阶段

> 在基础语法之上，掌握 Python 的四大内置容器：list、tuple、dict、set，能够按场景选择合适的数据结构，处理嵌套数据，写出清晰的推导式。

## 1. 概述

Python 数据结构阶段的目标是：**熟练使用 Python 最常用的内置容器，按场景选择合适的数据结构，处理嵌套数据，并写出可读性强的推导式**。这一阶段是后续函数、文件、面向对象和标准库的基础；list、dict、set 的熟练度直接决定日常脚本和数据处理的效率。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 有序可变序列 | list、切片、排序、遍历 |
| 有序不可变序列 | tuple、打包解包、可哈希性 |
| 键值映射 | dict、字典推导式、嵌套结构 |
| 集合与去重 | set、集合运算、集合推导式 |
| 遍历技巧 | enumerate、zip、dict.items |

**范围边界**：本阶段聚焦 Python 内置容器的基础与常用技巧，不涉及 `collections` 模块（如 `Counter`、`defaultdict`、`deque`）、生成器表达式深入、自定义类作为 dict key 的 `__hash__` 实现 — 那些是 **ph06 标准库**、**ph17 高级 Python**、**ph04 面向对象 OOP** 阶段的内容。

## 2. 来源与演变

Python 的数据结构深受 ABC 语言影响：ABC 用 `PUT` / `GET` 等自然语言风格操作表和列表，Python 继承了"用简单容器表达数据"的思想，同时加入了动态类型的灵活性。

| 设计源头 | 对 Python 容器的影响 |
|----------|---------------------|
| ABC 语言 | list、dict 等内置容器优先，语法贴近自然表达 |
| Duck typing | 不强制类型，只要求对象支持"协议"（如可迭代、可哈希） |
| Haskell / 集合论 | 列表推导式 `[x for x in xs]`、集合构建记号 `{x \| x in xs}` |
| 哈希表 | dict 和 set 的 O(1) 平均查找效率来源 |

Python 3.7 起，`dict` 保持插入顺序成为语言规范；3.6 只是在 CPython 实现中恰巧如此，不应依赖。`set` 是无序集合，不保证任何迭代顺序。

本文示例以 **Python 3.10+** 为基线（f-string、海象运算符、`dict` 插入有序均可用），本环境验证解释器为 Python 3.13.12。内置容器的核心语义自 Python 3.0 起稳定。

## 3. 语法与参数

### 3.1 list 深入

list 是有序、可变、允许元素重复的序列。ph01 已经介绍了 `append`、`insert`、`remove`、`pop`、索引和基础切片；本阶段重点是**排序、切片高级用法和作为记录集容器**。

```python
scores = [78, 92, 85, 67, 88]

# 排序：sort 原地修改，sorted 返回新列表
ascending = sorted(scores)
scores.sort(reverse=True)
print(ascending)   # [67, 78, 85, 88, 92]
print(scores)      # [92, 88, 85, 78, 67]

# 按字符串长度排序
words = ["apple", "kiwi", "banana", "pear"]
print(sorted(words, key=len))  # ['kiwi', 'pear', 'apple', 'banana']

# 合并列表
a = [1, 2]
b = [3, 4]
a.extend(b)        # 原地扩展
print(a)           # [1, 2, 3, 4]
print(a + [5, 6])  # [1, 2, 3, 4, 5, 6]（返回新列表）

# 判断成员
print(85 in scores)  # True
```

### 3.2 tuple

tuple 是有序、不可变的序列。因为不可变，tuple 通常用于保存不应被修改的记录，也更容易保证线程安全和作为 dict 的 key。

```python
point = (3, 5)
# point[0] = 4  # TypeError: tuple 不可变

# 打包与解包
coord = (120.5, 30.2)
x, y = coord
print(x, y)

# 用于函数多返回值
def min_max(nums):
    return min(nums), max(nums)

low, high = min_max([3, 1, 4, 1, 5])
print(low, high)  # 1 5

# tuple 作为 dict key（因为不可变，可哈希）
locations = {
    (0, 0): "origin",
    (1, 0): "east",
}
print(locations[(0, 0)])  # origin
```

> **注意**：tuple 的"不可变"是指 tuple 本身不可变，如果 tuple 内部包含 list，那个 list 仍然可以被修改。

### 3.3 dict

dict 是键值映射容器，Python 3.7+ 保证按插入顺序迭代。键必须可哈希，值可以是任意对象。

```python
user = {"name": "Alice", "age": 25}
user["city"] = "Shanghai"

# 安全取值
print(user.get("email", "unknown"))  # unknown

# 遍历键值对
for key, value in user.items():
    print(f"{key}: {value}")

# 批量更新
extra = {"age": 26, "email": "alice@example.com"}
user.update(extra)
print(user)

# 键和值
print(list(user.keys()))
print(list(user.values()))
```

### 3.4 set

set 是无序、不重复的元素集合，支持数学上的交、并、差运算，适合去重和成员判断。

```python
a = {1, 2, 3, 3, 3}  # 重复会被忽略
print(a)             # {1, 2, 3}

b = {2, 3, 4}
print(a & b)         # {2, 3}  交集
print(a | b)         # {1, 2, 3, 4}  并集
print(a - b)         # {1}  差集
print(a ^ b)         # {1, 4}  对称差集

# 去重
raw = ["apple", "banana", "apple", "orange", "banana"]
print(list(set(raw)))
```

### 3.5 切片完整形式

切片的基本形式是 `[start:stop:step]`，`start` 包含，`stop` 不包含；三者均可省略。负步长表示从后向前。

```python
nums = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

print(nums[2:6])      # [2, 3, 4, 5]
print(nums[:4])       # [0, 1, 2, 3]
print(nums[6:])       # [6, 7, 8, 9]
print(nums[::2])      # [0, 2, 4, 6, 8]
print(nums[::-1])     # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
print(nums[8:3:-1])   # [8, 7, 6, 5, 4]

# 拷贝（浅拷贝）
copy = nums[:]
print(copy)
```

| 切片 | 含义 |
|------|------|
| `s[:]` | 完整浅拷贝 |
| `s[::-1]` | 反转 |
| `s[::2]` | 每隔一个取一个 |
| `s[1:5]` | 取索引 1、2、3、4 |
| `s[-3:]` | 最后三个元素 |

### 3.6 推导式

推导式是把循环和条件压缩到一行的语法，能显著提升可读性——但条件是**保持可读**。如果一行推导式难以理解，就展开成普通循环。

```python
# 列表推导式
squares = [x * x for x in range(6)]
print(squares)  # [0, 1, 4, 9, 16, 25]

# 带条件
evens = [x for x in range(10) if x % 2 == 0]
print(evens)  # [0, 2, 4, 6, 8]

# 字典推导式
words = ["apple", "banana", "kiwi"]
length_map = {w: len(w) for w in words}
print(length_map)  # {'apple': 5, 'banana': 6, 'kiwi': 4}

# 集合推导式
chars = {c.lower() for c in "Hello World" if c.isalpha()}
print(chars)  # {'h', 'e', 'l', 'o', 'w', 'r', 'd'}
```

**可读性边界**：嵌套推导式（如 `[x for y in z for x in y]`）通常不如普通循环清晰；带多重条件的长推导式也建议展开。

### 3.7 排序 key

`sorted` 和 `list.sort` 都支持 `key` 参数，key 是一个函数，用于从元素中提取比较依据。

```python
students = [
    {"name": "Alice", "score": 85},
    {"name": "Bob", "score": 92},
    {"name": "Carol", "score": 78},
]

# 按分数降序
ranked = sorted(students, key=lambda s: s["score"], reverse=True)
for s in ranked:
    print(s["name"], s["score"])
```

### 3.8 遍历技巧

```python
names = ["Alice", "Bob", "Carol"]
scores = [85, 92, 78]

# 同时需要索引和值
for i, name in enumerate(names):
    print(f"{i}: {name}")

# 并行遍历多个序列
for name, score in zip(names, scores):
    print(f"{name}: {score}")

# dict 键值对遍历
info = {"a": 1, "b": 2}
for key, value in info.items():
    print(key, value)
```

## 4. 底层原理

### 4.1 list 的动态数组

Python list 底层是**动态数组**（dynamic array/over-allocated array）。当 append 导致容量不足时，CPython 会申请一个更大的连续内存块，并把旧元素复制过去。扩容策略采用**摊还分析**：虽然某一次扩容需要 O(n) 复制，但多次 append 的平均代价接近 O(1)。

```python
nums = []
for i in range(1000):
    nums.append(i)  # 平均 O(1)
```

也因此，list 在**头部或中间插入/删除**需要搬移元素，时间复杂度为 O(n)；频繁在头部操作时应考虑 `collections.deque`。

### 4.2 dict 与 set 的哈希表

dict 和 set 底层都是**哈希表**（hash table）。dict 把键通过哈希函数映射到表中的槽位，从而实现平均 O(1) 的查找、插入和删除。set 可视为只有键没有值的 dict。

**可哈希性**（hashable）是 dict key 和 set 元素的要求：

- 对象在生命周期内哈希值不变
- 对象支持 `__hash__()` 和 `__eq__()`
- 不可变类型（int、str、tuple、float、bool）通常可哈希
- 可变类型（list、dict、set）不可哈希

```python
# list 不能作为 dict key 或 set 元素
# d = {[]: 1}  # TypeError: unhashable type: 'list'
# s = {[1, 2]}  # TypeError

# tuple 可以（只要内部没有可变对象）
d = {(1, 2): "point"}
print(d[(1, 2)])
```

### 4.3 tuple 为什么可哈希

tuple 本身不可变，因此可以作为 dict key。但如果 tuple 内部包含 list，整个 tuple 就不再可哈希。

```python
t1 = (1, 2, 3)
print(hash(t1))  # 合法

t2 = (1, [2], 3)
# hash(t2)  # TypeError: unhashable type: 'list'
```

理解这一点对避免"把嵌套 list 当 key"的报错至关重要。

### 4.4 dict 插入顺序保证

Python 3.7 起，dict 保持插入顺序是语言规范，不再只是 CPython 实现细节。这意味着可以依赖 dict 的遍历顺序与插入顺序一致。

```python
order = {"first": 1, "second": 2, "third": 3}
print(list(order.keys()))  # ['first', 'second', 'third']
```

set 没有这种保证；如果需要有序且不重复，应使用 `dict.fromkeys()` 或后续阶段学习的 `collections.OrderedDict`。

## 5. 使用场景

| 场景 | 推荐结构 | 原因 |
|------|---------|------|
| 按顺序管理一组成绩 | list | 有序、可变、支持排序和切片 |
| 保存经纬度坐标 | tuple | 不可变、可哈希、可作为 dict key |
| 存储用户信息字段 | dict | 键值访问清晰、可读性高 |
| 去重或集合运算 | set | 自动去重、支持交并差 |
| 同时遍历索引和值 | enumerate + list | 避免手动维护计数器 |
| 并行遍历两个序列 | zip | 代码简洁、自动以最短的为准 |
| 表达记录集合 | list of dict | 结构化、易于扩展字段 |

**不适合用内置容器直接解决的事项**：

- 需要在两端频繁插入删除：用 `collections.deque`
- 需要计数并快速获取最高频项：用 `collections.Counter`
- 需要默认值的嵌套 dict：用 `collections.defaultdict`
- 需要保持插入顺序的去重：用 `dict.fromkeys()` 或 `collections.OrderedDict`
- 需要大量数学矩阵运算：用 NumPy（第三方库）

**本阶段高频坑自查表**：

| 坑 | 症状 | 修法 |
|----|------|------|
| 单元素 tuple 忘逗号 | `type((5))` 是 `int` 不是 `tuple` | 写 `(5,)`——逗号才是 tuple 的标记 |
| 大列表上反复 `x in list` | 越来越慢（O(n) × 次数） | 只需判断成员就转 `set`（O(1)）；需要保序就 `dict.fromkeys` 去重 |
| 遍历时增删容器 | `RuntimeError: dictionary changed size during iteration` | 收集要删的项，遍历完再删（或用推导式重建） |
| `b = a` 当拷贝用 | 改 `b` 影响了 `a` | 要独立副本用 `a[:]` / `list(a)`（浅拷贝；嵌套结构的深拷贝在 ph04 展开，ph01 的 4.5 已埋线） |
| `sorted(s)` 忘赋值 | 原序列"没变化"——sorted 返回新列表不原地改 | 记住：`sort()` 原地、`sorted()` 返回新对象 |
| `zip` 静默截断 | 两序列长度不同，结果悄悄少了一截 | 长度必然对齐才用 zip；否则先校验长度（或后续阶段学 `zip_longest`） |
| 遍历 dict 想拿"删除后的快照" | 边删边遍历报错 | `for k in list(d.keys()):`——先拷出键列表再遍历 |

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.py`，已在本环境用 Python 3.13.12 验证通过（示例 5 需要输入，验证时通过管道喂入）。

### 示例 1：成绩管理

完整文件：`examples/ex01-scores.py`

```python
scores = [78, 92, 85, 67, 88, 91, 73]

# 1. 计算平均分
average = sum(scores) / len(scores)
print(f"平均分: {average:.2f}")

# 2. 排序并取前三名
ranked = sorted(scores, reverse=True)
top3 = ranked[:3]
print(f"前三名: {top3}")

# 3. 及格人数
passed = [s for s in scores if s >= 60]
print(f"及格人数: {len(passed)}")

# 4. 每个分数加 5 分（最高不超过 100）
bonus = [min(s + 5, 100) for s in scores]
print(f"加分后: {bonus}")
```

### 示例 2：通讯录

完整文件：`examples/ex02-contacts.py`

```python
contacts = {
    "Alice": {"phone": "13800138000", "city": "Shanghai"},
    "Bob": {"phone": "13900139000", "city": "Beijing"},
}

# 添加联系人
contacts["Carol"] = {"phone": "13700137000", "city": "Shenzhen"}

# 查询
name = "Bob"
info = contacts.get(name)
if info:
    print(f"{name}: {info['phone']}, {info['city']}")
else:
    print(f"未找到 {name}")

# 列出所有城市
for name, info in contacts.items():
    print(f"{name} 住在 {info['city']}")
```

### 示例 3：购物车

完整文件：`examples/ex03-cart.py`

```python
# 购物车：列表中的每个元素是一个 dict，表示一条记录
cart = [
    {"name": "apple", "price": 5.5, "quantity": 3},
    {"name": "banana", "price": 3.0, "quantity": 2},
    {"name": "milk", "price": 12.0, "quantity": 1},
]

# 计算总价
total = sum(item["price"] * item["quantity"] for item in cart)
print(f"总价: {total:.2f}")

# 按单价排序
sorted_cart = sorted(cart, key=lambda x: x["price"])
for item in sorted_cart:
    print(f"{item['name']}: {item['price']} x {item['quantity']}")
```

### 示例 4：词频统计

完整文件：`examples/ex04-word-freq.py`

```python
text = "apple banana apple orange banana apple"
words = text.split()

# 统计词频
freq = {}
for w in words:
    freq[w] = freq.get(w, 0) + 1

# 按频率降序输出
for word, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
    print(f"{word}: {count}")

# 使用 set 去重停用词
stopwords = {"the", "a", "is"}
unique_words = set(words)
print(f"不重复词数: {len(unique_words - stopwords)}")
```

### 示例 5：读取多行输入并分组

完整文件：`examples/ex05-group-input.py`

```python
# 输入格式：每行 "姓名 分数"，以空行结束（或用 EOF 结束）
# 示例输入：
# Alice 85
# Bob 92
# Carol 78
#
# 下面的代码读取标准输入直到 EOF
import sys

groups = {"优秀": [], "良好": [], "及格": [], "不及格": []}

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    name, score_str = line.split()
    score = int(score_str)
    if score >= 90:
        groups["优秀"].append(name)
    elif score >= 80:
        groups["良好"].append(name)
    elif score >= 60:
        groups["及格"].append(name)
    else:
        groups["不及格"].append(name)

for level, names in groups.items():
    print(f"{level}: {names}")
```

## 7. 总结

### 关键要点

1. **list 是有序可变序列**：适合管理同类元素，append 平均 O(1)，但中间插入/删除是 O(n)
2. **tuple 是不可变序列**：通常用于记录、多返回值和作为 dict key
3. **dict 是键值映射**：Python 3.7+ 保证插入顺序；key 必须可哈希
4. **set 是无序不重复集合**：适合去重和集合运算
5. **切片完整形式是 `[start:stop:step]`**：负步长用于反转，省略参数表示从头/到尾
6. **推导式要服务于可读性**：复杂逻辑优先使用普通循环
7. **sorted 的 key 参数**让按属性排序变得简洁
8. **嵌套结构（list of dict）是表达记录集的常用方式**
9. **复杂度是选结构的判据**：成员判断 list 是 O(n)、set/dict 是 O(1)（大量 `in` 检查先转 set）；dict 保插入序、set 无序——"去重且保序"用 `dict.fromkeys`（3.7+ 插入序规范）
10. **别名与拷贝要分清**：`b = a` 是绑定同一对象，要独立副本用切片/`list()`；不可变对象才能当 dict key、set 元素（4.2/4.3）

### 跨语言对比：数据结构

| Python | Go | Java | Rust |
|--------|-----|------|------|
| list | slice | `ArrayList` / `List` | `Vec` |
| tuple | 无直接对应 | 无直接对应 | tuple（如 `(i32, i32)`） |
| dict | map | `HashMap` / `Map` | `HashMap` |
| set | 无内置 set（可用 map 模拟） | `HashSet` / `Set` | `HashSet` |
| 列表推导式 | 无 | Stream API | iterator + collect |
| 动态类型 | 静态 | 静态 | 静态 |

### 阶段验收清单

- [ ] 能按场景选择 list、tuple、dict、set
- [ ] 能熟练使用完整切片 `[start:stop:step]`
- [ ] 能处理嵌套 dict 和 list of dict
- [ ] 能写出清晰的列表、字典、集合推导式
- [ ] 能用 `sorted` 的 `key` 按属性排序
- [ ] 能用 `enumerate`、`zip`、`dict.items` 完成常见遍历

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：购物车 —— 用 list of dict 管理商品，支持添加/删除商品、计算总价、按价格排序、交互式操作。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[函数与模块化阶段](../ph03-func-module/03-func-module.md) — 参数进阶、作用域、模块与包。
