# Python 函数与模块化阶段

> 在数据结构之上，掌握 Python 函数的参数体系、作用域规则和模块组织方式，能够把代码拆成职责清晰的函数，组织为可复用的模块和包。

## 1. 概述

Python 函数与模块化阶段的目标是：**能设计清晰的函数参数和返回值，理解 Python 的完整参数传递体系，掌握 LEGB 作用域规则，用模块和包组织多文件项目，并避免可变默认参数等常见陷阱**。这一阶段是后续面向对象、标准库和项目工程化的基础；函数接口设计的质量直接决定代码的可读性、可测试性和可复用性。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 函数定义与调用 | `def`、`return`、多返回值、文档字符串 |
| 参数完整体系 | 位置、默认、仅限位置、仅限关键字、`*args`、`**kwargs` |
| 函数即对象 | 一等公民：赋值、传参、返回、`lambda` |
| 作用域 | LEGB 规则：Local → Enclosing → Global → Built-in |
| 模块与包 | `import` 四种写法、`__init__.py`、`if __name__ == "__main__"` |

**范围边界**：本阶段聚焦函数基础、参数体系和模块化组织，不涉及闭包深入、装饰器、生成器（`yield`）、迭代器协议、`functools` 等高级特性 — 那些是 **ph17 高级 Python**、**ph06 标准库** 阶段的内容。

## 2. 来源与演变

Python 的函数设计从 ABC 语言继承而来，同时吸收了函数式语言和现代软件工程实践。

| 设计源头 | 对 Python 函数/模块的影响 |
|----------|--------------------------|
| ABC 语言 | `HOW TO` / `RETURN` 语法原型；用缩进定义代码块 |
| Lisp / 函数式 | 函数是一等对象，`lambda` 匿名函数 |
| Modula-3 | 模块系统原型：`import` 机制、命名空间隔离 |
| PEP 3102（Python 3.0） | 仅限关键字参数：`def f(*, a, b)`，`*` 之后必须用关键字传参 |
| PEP 570（Python 3.8） | 仅限位置参数：`def f(a, b, /)`，`/` 之前禁止用关键字传参 |

PEP 3102 解决了"调用时参数名写错但位置碰巧对上"的隐蔽 bug；PEP 570 让内置函数（如 `len(obj, /)`）的参数语义在纯 Python 中也能表达。两个 PEP 共同定义了 Python 的完整参数传递模型。

本文示例以 **Python 3.10+** 为基线（f-string、海象运算符、仅位置参数标记 `/` 均可用），本环境验证解释器为 Python 3.13.12。函数定义、参数传递与模块导入的核心语义自 Python 3.0 起稳定。

## 3. 语法与参数

### 3.1 函数定义基础

```python
def greet(name, greeting="Hello"):
    """返回问候语。"""
    return f"{greeting}, {name}!"

print(greet("Alice"))                      # Hello, Alice!
print(greet("Bob", greeting="Hi"))         # Hi, Bob!
print(greet(greeting="Hey", name="Carol")) # Hey, Carol!
```

`def` 定义函数，缩进界定函数体。`return` 返回结果，无显式 `return` 时返回 `None`。多返回值底层是打包成 tuple：

```python
def divide(a, b):
    return a // b, a % b

q, r = divide(10, 3)
print(q, r)         # 1 3
print(divide(10, 3))  # (1, 3) —— 实际上返回一个 tuple
```

### 3.2 参数类型完整体系

Python 的参数传递模型是六种参数类型的组合，定义时从严格到灵活排列。以下函数展示完整体系：

```python
def describe(a, b, /, c, d=10, *args, e, f=20, **kwargs):
    """a,b 仅限位置 | c,d 位置/关键字 | *args 打包 | e,f 仅限关键字 | **kwargs 打包"""
    return a, b, c, d, args, e, f, kwargs

r = describe(1, 2, 3, e=5)
print(r)  # (1, 2, 3, 10, (), 5, 20, {})

r = describe(1, 2, 3, 4, 99, 100, e=5, f=6, x=7, y=8)
print(r)  # (1, 2, 3, 4, (99, 100), 5, 6, {'x': 7, 'y': 8})
```

| 参数类型 | 定义写法 | 调用约束 | 说明 |
|----------|---------|---------|------|
| 位置参数 | `def f(x)` | `f(1)` | 按位置匹配，必传 |
| 默认参数 | `def f(x=10)` | `f()` 或 `f(5)` | 省略时用默认值 |
| 仅限位置（3.8+） | `def f(x, /)` | `f(1)` | 不能 `f(x=1)` |
| 仅限关键字 | `def f(*, x)` | `f(x=1)` | 必须 `f(x=1)`，不能按位置传 |
| `*args` | `def f(*args)` | `f(1,2,3)` | 多余位置参数打包为 tuple |
| `**kwargs` | `def f(**kwargs)` | `f(a=1)` | 多余关键字参数打包为 dict |

**定义顺序**：`def f(pos1, pos2, /, pos_or_kw, *args, kw_only, **kwargs)`。

### 3.3 可变默认参数陷阱

这是 Python 最常见也最隐蔽的坑之一：**默认参数值在函数定义时只计算一次**。如果默认值是可变对象（list、dict、set），每次调用默认参数的调用者共享同一个对象。

```python
# 错误写法 —— 每次调用共享同一个 list
def add_item(item, target=[]):
    target.append(item)
    return target

print(add_item(1))  # [1]
print(add_item(2))  # [1, 2]  —— 预期是 [2]，实际上次结果还在
print(add_item(3))  # [1, 2, 3]  —— 越来越长
```

原因：`def` 执行时 `[]` 只创建一次，之后不传 `target` 的调用共享同一个 list 对象。

```python
# 正确写法 —— 用 None 做哨兵值
def add_item(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target

print(add_item(1))  # [1]
print(add_item(2))  # [2]  —— 符合预期
print(add_item(3))  # [3]
```

### 3.4 *args 和 **kwargs：打包与拆包

`*` 和 `**` 有两个方向：在**函数定义**中打包多余参数，在**函数调用**中拆包序列和映射。

```python
# 打包：收集多余参数
def log_all(level, *messages, **tags):
    print(f"[{level}]", " ".join(str(m) for m in messages))
    for k, v in tags.items():
        print(f"  {k}: {v}")

log_all("INFO", "server", "started", host="localhost", port=8080)

# 拆包：展开序列和映射
nums = [3, 1, 4, 1, 5]
print(*nums)  # 3 1 4 1 5 —— 展开为独立参数

config = {"host": "db.example.com", "port": 5432}
print("host={host}, port={port}".format(**config))
```

### 3.5 lambda 表达式

`lambda` 创建匿名函数，语法 `lambda 参数: 表达式`。**函数体必须是单一表达式**，不能包含语句（不可赋值、循环、`if` 语句）。最常见场景是 `sorted` 的 `key`：

```python
# 常见用法
records = [("Alice", 85), ("Bob", 92), ("Carol", 78)]
records.sort(key=lambda x: x[1], reverse=True)
print(records)  # [('Bob', 92), ('Alice', 85), ('Carol', 78)]

# 配合 map/filter
nums = [1, 2, 3, 4, 5]
print(list(map(lambda x: x * 2, nums)))    # [2, 4, 6, 8, 10]
print(list(filter(lambda x: x % 2 == 0, nums)))  # [2, 4]
```

**什么时候不该用 lambda**：逻辑超一行、需要赋值或循环时，直接用 `def`。复杂 lambda 损害可读性。

### 3.6 作用域 LEGB

Python 按 **LEGB** 顺序查找变量名：

| 作用域 | 含义 | 示例位置 |
|--------|------|---------|
| **L**ocal | 函数内部定义 | 函数内的变量 |
| **E**nclosing | 外层函数的局部作用域 | 嵌套函数中，内层访问外层的变量 |
| **G**lobal | 模块级别 | 文件顶层定义的变量 |
| **B**uilt-in | 内置名称空间 | `print`、`len`、`range` |

```python
x = "global"            # Global

def outer():
    x = "enclosing"     # Enclosing（对外层 inner 而言）

    def inner():
        x = "local"     # Local
        print(f"inner: {x}")     # local

    inner()
    print(f"outer: {x}")         # enclosing

outer()
print(f"global: {x}")            # global
```

修改外层变量需要 `global` 或 `nonlocal` 声明：

```python
count = 0

def increment():
    global count
    count += 1

def make_counter():
    total = 0
    def inner():
        nonlocal total
        total += 1
        return total
    return inner

increment()
print(count)         # 1
c = make_counter()
print(c(), c())      # 1 2
```

应优先用参数和返回值传递数据，避免滥用 `global`。

### 3.7 模块导入与包结构

模块是单个 `.py` 文件，导入有四种写法：`import math`（`math.sqrt(4)`）、`from math import sqrt`（`sqrt(4)`）、`import math as m`（`m.sqrt(4)`）、`from math import *`（不推荐，污染命名空间）。

模块在**首次导入时执行**，后续复用 `sys.modules` 缓存：`import sys, math; print(math is sys.modules["math"])  # True`。

包是包含 `__init__.py` 的目录（可为空，也可控制导出）。典型结构：`mylib/` 包目录含 `__init__.py`、`math_utils.py`、`string_utils.py` 等子模块。

`if __name__ == "__main__"` 实现**入口脚本和库代码分离**：

```python
# tools.py —— 可 import 也可直接运行
def add(a, b):
    return a + b

if __name__ == "__main__":
    print(add(1, 2))   # 仅直接运行时执行
```

## 4. 底层原理

### 4.1 函数是一等对象

Python 中函数是一等公民：可赋值给变量、作为参数传递、作为返回值、存入数据结构。

```python
def greet(name):
    return f"Hello, {name}!"

# 赋值给变量
say = greet
print(say("Alice"))                         # Hello, Alice!

# 作为参数传递
def apply(func, arg):
    return func(arg)
print(apply(greet, "Bob"))                  # Hello, Bob!

# 作为返回值
def make_greeting(formal):
    return lambda n: f"Dear {n}," if formal else f"Hi {n}!"
print(make_greeting(True)("Carol"))          # Dear Carol,

# 存入数据结构 —— 策略模式
ops = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b}
print(ops["add"](3, 5))                     # 8
```

这一特性让 Python 能自然地使用回调模式和高阶函数，无需额外的接口包装。

### 4.2 模块缓存与传参语义

**sys.modules 缓存**：导入时先查 `sys.modules`，命中直接返回；未命中则找到文件、编译、执行、缓存。同一模块在解释器生命周期中只执行一次，全局变量成为模块级"单例"。

**传参是传对象引用**（call by sharing）：不可变对象（int、str、tuple）的"修改"实为新对象，外部不可见；可变对象（list、dict、set）的修改直接影响原对象。

```python
def modify(num, lst):
    num += 1          # int 不可变 → 创建新对象，外部不受影响
    lst.append(4)     # list 可变 → 原地修改，外部可见

x = 10
items = [1, 2, 3]
modify(x, items)
print(x)       # 10 —— 未改变
print(items)   # [1, 2, 3, 4] —— 已改变
```

## 5. 使用场景

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 重复使用的计算逻辑 | `def` 函数 | 避免重复，单一职责 |
| 排序时的比较依据 | `key=lambda x: x.attr` | 简洁，不需要命名一次性函数 |
| 不确定参数个数 | `def f(*args, **kwargs)` | 灵活收集多余参数 |
| 防止参数名写错 | 仅限位置 `def f(a, /)` | 强制按位置，编译器可检测 |
| 提高 API 可读性 | 仅限关键字 `def f(*, timeout)` | `f(timeout=30)` 自解释 |
| 组织可复用代码 | 独立 `.py` 模块 | 命名空间隔离、import 缓存 |
| 脚本+库双用途 | `if __name__ == "__main__"` | 可导入、可独立运行 |
| 避免可变默认参数坑 | `None` 哨兵 + 函数体创建对象 | 每次调用获取独立对象 |

**不适合的事项**：

- 多次调用间保持可变状态并扩展行为：用类（ph04 OOP）
- 横切关注点（日志、计时）注入：用装饰器（高级 Python）
- 惰性生成大规模序列：用生成器 `yield`（高级 Python）
- 资源生命周期管理（文件、锁、连接）：用 `with`（文件操作阶段）

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.py`（多文件示例 3 用子目录 `ex03-math-module/` 组织），已在本环境用 python3 验证。

### 示例 1：可变默认参数 —— 从错误到纠正

完整文件：`examples/ex01-mutable-default.py`

```python
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
```

### 示例 2：*args/**kwargs 打包与拆包综合演示

完整文件：`examples/ex02-args-kwargs.py`

```python
def create_report(title, *sections, **options):
    """生成报告：title 必传，*sections 打包位置参数，**options 打包关键字参数。"""
    lines = [f"=== {title} ===", ""]
    for i, sec in enumerate(sections, 1):
        lines.append(f"  {i}. {sec}")
    for k, v in sorted(options.items()):
        lines.append(f"  [{k}] {v}")
    return "\n".join(lines)

# 打包调用
report = create_report(
    "2024 Q1", "Revenue up 12%", "New hires: 5",
    author="Alice", date="2024-04-01", confidential=True
)
print(report)
print()

# 拆包调用：*list → 位置参数，**dict → 关键字参数
headers = ["Monthly Report", "Overview"]
details = {"author": "Bob", "status": "draft"}
print(create_report(*headers, **details))
```

### 示例 3：数学工具模块

本示例演示多文件组织：工具模块 + 入口脚本。

完整文件：`examples/ex03-math-module/`（`math_utils.py` + `main_math.py`）

```python
# === math_utils.py ===
"""数学工具函数集合。"""

def is_prime(n):
    """判断 n 是否为质数。"""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

def factorial(n):
    """计算 n 的阶乘（n >= 0）。"""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def primes_up_to(limit):
    """返回 [2, limit] 范围内的所有质数。"""
    return [n for n in range(2, limit + 1) if is_prime(n)]
```

```python
# === main_math.py ===
import math_utils

print("7 is prime?", math_utils.is_prime(7))    # True
print("10 is prime?", math_utils.is_prime(10))  # False
print("5! =", math_utils.factorial(5))          # 120
print("primes <= 30:", math_utils.primes_up_to(30))
# [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

if __name__ == "__main__":
    print("main_math.py executed directly")
```

### 示例 4：LEGB 作用域完整追踪

完整文件：`examples/ex04-legb-scope.py`

```python
name = "Global"              # G: Global
PI = 3.14159                 # G: Global

def outer(prefix):
    name = "Outer"           # E: Enclosing
    multiplier = 10          # E: Enclosing

    def inner(value):
        name = "Inner"       # L: Local
        return f"[{name}] {prefix} {value}*{multiplier}={value * multiplier}"

    print(f"[{name}] {inner(7)}")   # multiplier → Enclosing
    print(f"[{name}] PI={PI}")      # PI → Global; print → Built-in

print(f"[{name}] before outer")
outer("val:")
print(f"[{name}] after outer")
```

### 示例 5：CLI 字符串工具

完整文件：`examples/ex05-strtools.py`

```python
"""字符串处理 CLI。用法：python3 strtools.py <count\|reverse\|stats> "text" """
import sys

def count_chars(text):
    return len([c for c in text if c != " "])

def reverse(text):
    return text[::-1]

def stats(text):
    return {
        "总字符": len(text),
        "字母": sum(1 for c in text if c.isalpha()),
        "数字": sum(1 for c in text if c.isdigit()),
        "空格": sum(1 for c in text if c.isspace()),
    }

COMMANDS = {"count": count_chars, "reverse": reverse, "stats": stats}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 strtools.py <count|reverse|stats> <text>")
        sys.exit(0)
    cmd, text = sys.argv[1], sys.argv[2]
    func = COMMANDS.get(cmd)
    if not func:
        print(f"未知命令: {cmd}，可用: {list(COMMANDS.keys())}")
        sys.exit(1)
    result = func(text)
    if isinstance(result, dict):
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print(result)
```

## 7. 总结

### 关键要点

1. **六类参数有严格顺序**：仅限位置（`/`）→ 位置/关键字 → `*args` → 仅限关键字 → `**kwargs`
2. **可变默认参数共享同一对象**：`def f(lst=[])` 是陷阱，用 `None` 哨兵值 + 函数体内创建新对象
3. **`*`/`**` 双向使用**：定义时打包，调用时拆包
4. **lambda 做小不做大**：单表达式用 `lambda`，多语句用 `def`
5. **LEGB 查找链**：L→E→G→B；修改外层需 `global`/`nonlocal`
6. **模块只执行一次**：`sys.modules` 缓存，首次 import 执行后后续直接复用
7. **`if __name__ == "__main__"`** 分离库代码和入口脚本
8. **函数是一等对象**：可赋值、传参、返回、存入容器
9. **传参是传对象引用**：可变对象修改对外可见，不可变对象"修改"是新对象

### 跨语言对比：函数与模块

| Python | Go | Java | Rust |
|--------|-----|------|------|
| `def` | `func` | method（在 class 内） | `fn` |
| 默认/关键字参数 | 无 | 无 | 无 |
| `*args` 打包 | `...int` | `int...` varargs | 无 |
| `**kwargs` 打包 | 无 | 无 | 无 |
| `lambda` | 匿名函数 | `(x) -> x * 2` | `\|x\| x * 2` |
| 模块系统 | `import` | `import` | `use` / `mod` |
| 入口模式 | `if __name__ == "__main__"` | `package main` + `func main()` | `main` 方法 | `fn main()` |

### 阶段验收清单

- [ ] 能设计函数参数和返回值，合理选择参数类型（何时用仅限位置/仅限关键字）
- [ ] 能组织多文件项目，正确使用 `import` 和 `if __name__ == "__main__"`
- [ ] 能避免可变默认参数问题，并解释根本原因（默认值在 `def` 时计算一次）
- [ ] 能解释 LEGB 作用域查找规则，在嵌套函数中追踪变量归属
- [ ] 能写出 `*args`/`**kwargs` 的打包和拆包语句
- [ ] 能判断何时用 `lambda`、何时用 `def`

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：CLI 工具（`txtool` 文本文件工具箱，用 `sys.argv` 解析子命令，命令处理函数按模块组织，支持 `--help` 和子命令）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[面向对象 OOP 阶段](../ph04-oop/04-oop.md) — class 定义、`__init__`、实例变量与类变量、继承与多态、property 与魔术方法。
