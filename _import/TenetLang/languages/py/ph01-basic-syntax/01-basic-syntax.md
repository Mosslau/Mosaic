# Python 基础语法阶段

> 面向自动化、数据分析、AI 原型和快速开发方向，从解释器、动态类型和可读性优先的语法起步。

## 1. 概述

Python 基础语法阶段的目标是：**能写简单 Python 程序，理解解释器、脚本和基础语法**。Python 的设计哲学是"可读性优先"（Readability counts），语法简洁直观，适合快速验证想法。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 环境 | Python 安装、解释器、REPL |
| 数据 | 变量、`int`/`float`/`bool`/`str`/`None` |
| 控制流 | 运算符、条件判断（`if`/`elif`/`else`）、循环（`for`/`while`） |
| 函数 | `def`、参数、返回值 |
| I/O | `print`、`input`、字符串格式化 |

与其他语言不同，Python 在基础阶段就可以写**完整可用的工具脚本**——这得益于动态类型和丰富的内置功能。

这个阶段只涉及单脚本的顺序、分支、循环和简单函数，**不涉及类与面向对象、模块分包、文件读写和第三方库** — 那些是 ph03 函数与模块化、ph04 面向对象、ph05 文件操作阶段的内容。

## 2. 来源与演变

Python 由 Guido van Rossum 于 1991 年发布。设计目标是一门**易读、表达力强**的脚本语言，名字来源于英国喜剧团体 Monty Python。

| 版本 | 年份 | 标志性变化 |
|------|------|-----------|
| Python 1.0 | 1994 | 函数式工具（lambda, map, filter） |
| Python 2.0 | 2000 | 列表推导式、垃圾回收、Unicode |
| Python 3.0 | 2008 | 不兼容大版本：`print` 改为函数、Unicode 默认、`range()` 变为惰性序列 |
| Python 3.5 | 2015 | 类型注解（PEP 484）、`async`/`await`（PEP 492） |
| Python 3.6 | 2016 | **f-string**（`f"{name}"`）、数字字面量下划线（`1_000_000`）、变量注解（PEP 526） |
| Python 3.10 | 2021 | 结构模式匹配（`match`/`case`） |
| Python 3.12 | 2023 | 改进的错误消息、每个子解释器的 GIL |

> **重要**：Python 2 已于 2020 年停止维护，所有新的学习必须基于 **Python 3**。

## 3. 语法与参数

### 3.1 第一个程序

```python
# 这是单行注释
print("Hello, Python")  # 行尾也可以写注释
```

就这么简单——不需要 `main` 函数、不需要分号、不需要类型声明。Python 是**脚本式**的执行：从上到下逐行执行。

Python 只有 `#` 单行注释；多行说明用连续的 `#`，函数/模块的文档则用三引号文档字符串（docstring，见下文「函数基础」一节）。

### 3.2 变量与基本类型

```python
name = "Python"         # str — 字符串
age = 30                # int — 整数（无大小限制，自动扩展）
pi = 3.14159            # float — 浮点数（双精度）
is_active = True        # bool — 布尔值（首字母大写）
nothing = None          # NoneType — 空值

# 类型检查
print(type(name))       # <class 'str'>
print(type(age))        # <class 'int'>

# 类型转换
score_str = "95"
score = int(score_str)  # 字符串 → 整数
```

**关键概念**：
- Python 是**动态类型**（Dynamic Typing）语言——变量名绑定到对象，类型属于对象不属于变量
- 同一个变量可以在不同时刻指向不同类型的对象
- 整数（`int`）没有溢出限制，可以无限大（受内存限制）

### 3.3 字符串

```python
name = "Alice"
greeting = 'Hello'        # 单引号和双引号等效

# 字符串操作
full = name + " Smith"    # 拼接
repeated = "Hi" * 3       # "HiHiHi"
length = len(full)        # 长度

# f-string（Python 3.6+，推荐写法）
age = 30
print(f"Hello, {name}. You are {age} years old.")
print(f"2 + 2 = {2 + 2}")

# 方法
print(name.upper())       # "ALICE"
print(name.lower())       # "alice"
print("  hello  ".strip())   # "hello"
print("a,b,c".split(","))    # ['a', 'b', 'c']
```

**字符串方法速查（本阶段够用的一组）**——字符串方法是文本处理的主力，会查文档即可，但下面这组是日常最高频的：

| 方法 | 作用 | 示例 |
|------|------|------|
| `strip()` / `lstrip()` / `rstrip()` | 去首尾 / 左 / 右空白 | `" x ".strip()` → `"x"` |
| `replace(old, new)` | 替换（全部出现） | `"a-b-c".replace("-", "/")` → `"a/b/c"` |
| `startswith` / `endswith` | 前缀 / 后缀判断 | `name.endswith(".py")` |
| `split(sep)` / `"sep".join(list)` | 拆成列表 / 拼回字符串 | `"-".join(["a","b"])` → `"a-b"` |
| `find(sub)` / `index(sub)` | 找子串位置（找不到：`-1` / 抛异常） | `"hello".find("l")` → 2 |
| `count(sub)` | 子串出现次数 | `"banana".count("a")` → 3 |
| `isdigit()` / `isalpha()` | 是否全数字 / 全字母 | `"123".isdigit()` → `True` |

三种拼字符串的方式要分清：**少量拼接用 `+`（`"a" + "b"`）、格式化输出用 f-string、批量拼接用 `join`**——`join` 是"把一堆片段拼成一个字符串"的标准姿势（`"".join(parts)`），它比循环里反复 `+=` 快得多（性能话题在后续阶段展开，这里先养成用 join 的习惯）。

### 3.4 输入输出

```python
# 输出
print("Hello", "World", sep=", ", end="!\n")

# 输入（返回字符串）
name = input("What is your name? ")
age = int(input("How old are you? "))    # 需要手动类型转换
print(f"{name} is {age} years old.")
```

### 3.5 运算符

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / // % **` | `7 // 2` → `3`、`2 ** 10` → `1024` |
| 关系 | `== != < > <= >=` | `a == b` |
| 逻辑 | `and or not` | `a > 0 and b > 0` |
| 赋值 | `= += -= *= /=` | `x += 1` |
| 成员 | `in`、`not in` | `"a" in "abc"` → `True` |
| 身份 | `is`、`is not` | `x is None` |

**注意**：
- `/` 总是返回 `float`（`7 / 2` → `3.5`），整除用 `//`，幂用 `**`
- Python **没有** `++`/`--`，用 `x += 1`
- 逻辑运算符是单词 `and`/`or`/`not`，不是 `&&`/`||`/`!`
- 判断 `None` 用 `is`，不用 `==`

**真值判断（Python 特有的习惯）**——除了 `True`/`False`，Python 把很多值也当"假"处理（falsy），这让条件判断非常简洁：

```python
# falsy 值：None、False、0、0.0、""、[]、()、{} —— 其余都是 truthy
if not items:        # 列表为空时进入——等价于 if len(items) == 0，但更地道
    print("空列表")
if name:             # 非空字符串才进入——直接拿"有没有内容"当条件
    print(f"你好，{name}")
```

| 写法 | 等价的长写法 | 说明 |
|------|-------------|------|
| `if not items:` | `if len(items) == 0:` | 判空用真值，别数长度 |
| `if name:` | `if name != "":` | 判断"有内容" |
| `if x is None:` | — | 判 None 用 `is`，不是 `==` |
| `0 <= x < 10` | `x >= 0 and x < 10` | **比较链**：数学式写法直接可用 |

这套"真值即条件"的习惯是 Pythonic 代码的第一课——**`if` 后面直接放"有意义的对象"而不是比较式**，读起来几乎像自然语言。

### 3.6 控制流

**条件判断 — 缩进是语法**：

```python
score = 85

if score >= 90:
    print("A")
elif score >= 80:
    print("B")
elif score >= 60:
    print("C")
else:
    print("F")
```

**缩进（Indentation）是 Python 语法的核心**：同一层级的代码必须有相同的缩进量。推荐用 4 个空格。

**for 循环 — 遍历可迭代对象**：

```python
# 字符串遍历
for ch in "hello":
    print(ch)

# 范围遍历
for i in range(5):       # 0, 1, 2, 3, 4
    print(i)

for i in range(2, 10, 3):  # 2, 5, 8 (start, stop, step)
    print(i)

# 列表遍历
fruits = ["apple", "banana", "orange"]
for i, fruit in enumerate(fruits):   # enumerate 获取索引
    print(f"{i}: {fruit}")
```

**while 循环**：

```python
count = 5
while count > 0:
    print(count)
    count -= 1   # 没有 count-- 语法，只能用 count -= 1
```

**break 和 continue**：与 C/C++ 含义相同，作用于最内层循环。

### 3.7 函数基础

```python
def greet(name, greeting="Hello"):
    """返回问候语。（这是 docstring）"""
    return f"{greeting}, {name}!"

# 调用
print(greet("Alice"))              # Hello, Alice!
print(greet("Bob", "Hi"))          # Hi, Bob!
print(greet(greeting="Hey", name="Carol"))  # 关键字参数
```

| 特性 | 说明 |
|------|------|
| `def` | 定义函数 |
| 参数 | 无类型声明，位置参数、默认参数、关键字参数 |
| 返回值 | `return` 返回，无 `return` 则返回 `None` |
| docstring | `"""..."""` 文档字符串 |

### 3.8 列表（List）初步

```python
# 列表：可变、有序、元素可不同类型
fruits = ["apple", "banana", "orange"]
fruits.append("grape")        # 末尾添加
fruits.insert(1, "kiwi")      # 指定位置插入
fruits.remove("banana")       # 按值删除
last = fruits.pop()           # 弹出最后一个
print(fruits[0])              # 索引访问
print(fruits[-1])             # 倒数第一个
print(len(fruits))            # 长度

# 切片
print(fruits[1:3])            # ['kiwi', 'orange']
print(fruits[::-1])           # 反转
```

## 4. 底层原理

### 4.1 解释器模型

```
python script.py  → Python 解释器逐行解析执行
python -c "print(1+2)"  → 直接执行一行代码
python  → 进入 REPL（交互式环境）
```

Python 代码**不需要手动编译步骤**。解释器在后台自动将源码编译为**字节码**（Bytecode）再执行。被 `import` 的模块会把字节码缓存在 `__pycache__/` 目录的 `.pyc` 文件中——下次导入时若源码未改动就直接加载缓存，跳过编译步骤；主脚本本身则每次运行都重新编译，不写入缓存。

**包管理工具**：

```bash
pip install requests       # 安装第三方包
pip list                   # 查看已安装的包
python -m venv myenv       # 创建虚拟环境（隔离项目依赖）
source myenv/bin/activate  # 激活虚拟环境（macOS/Linux）
```

> 基础阶段主要用标准库，了解 `pip` 和 `venv` 的概念即可。后续阶段会深入学习依赖管理。

### 4.2 动态类型的本质

```python
x = 42          # x 指向 int 对象 42
x = "hello"     # x 指向 str 对象 "hello"——完全合法
```

变量名只是**名称标签**，指向内存中的对象。对象有类型，标签没有类型。这就是**动态类型**（Dynamic Typing）：它提供了极大的灵活性，但放弃了编译期类型检查。

与之相关的是**鸭子类型**（Duck Typing）——"如果它走起来像鸭子、叫起来像鸭子，那它就是鸭子"：调用方只关心对象有没有需要的方法，不关心对象的具体类型。这是 Python 多态的基础，OOP 阶段会深入。

### 4.3 缩进即语法

```python
if True:
    print("in block")
    print("still in block")
print("outside block")  # 缩进结束 = 代码块结束
```

Python 用缩进替代 `{}` 或 `begin/end` 来定义代码块。好处是代码天然整洁，代价是混用 tab 和空格会导致难以排查的 `IndentationError`。

### 4.4 不可变 vs 可变

```python
# 不可变（Immutable）：int, float, str, tuple, bool, None
s = "hello"
# s[0] = "H"  # TypeError! 字符串不可修改
s = "H" + s[1:]  # 正确：创建新字符串

# 可变（Mutable）：list, dict, set
nums = [1, 2, 3]
nums[0] = 10  # 合法：列表可以原地修改
```

理解可变和不可变的区别，是后续避免 bug 的关键。

### 4.5 变量是名字：引用与别名的第一课

4.2 说"变量名只是标签"——落到代码上是**赋值 = 把名字绑定到对象**，两个名字可以指向同一个对象：

```python
a = [1, 2, 3]
b = a              # b 与 a 指向同一个列表对象（不是拷贝！）
b.append(4)
print(a)           # [1, 2, 3, 4] —— a 也变了，因为 a、b 是同一个对象的两个名字

c = a[:]           # 切片创建新列表（浅拷贝）
c.append(5)
print(a)           # [1, 2, 3, 4] —— 切片后互不影响
```

| 代码 | 发生了什么 |
|------|-----------|
| `b = a` | **别名**：两个名字绑到同一对象，改一个另一个也变 |
| `b = a[:]` | **新列表**：复制元素到新对象，之后互不影响（嵌套结构另有深拷贝话题，ph02 展开） |
| `s = "hi"` | 字符串不可变，任何"修改"都产生新对象——**别名在不可变对象上无害** |

判断"改这里会不会影响那里"只需要问一句：**两个名字指向的是不是同一个对象？**——可变对象（list/dict/set）的别名要当心，不可变对象（str/int/tuple）随便别名。函数传参也是"把实参绑到形参名"，所以**函数内改传入的列表会影响到调用方**——这既是 Python 的能力也是新手最常见的意外来源（函数的参数语义在 ph03 函数与模块化阶段系统展开，这里先建立"传的是引用不是值"的直觉）。

## 5. 使用场景

基础语法阶段适合解决的问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 计算器 | 变量、算术、函数 |
| 猜数字游戏 | 循环、条件、输入输出 |
| 字符统计 | 字符串方法、字典 |
| 成绩判定 | if/elif 分支 |
| 数据处理脚本 | 列表、循环、打印 |

Python 在基础阶段就能写出很多实用的脚本——这是动态语言的优势。

**本阶段在 Python 路线里的位置**（后续阶段从这里长出来）：

| 后续阶段 | 承接本阶段的什么 |
|---------|----------------|
| ph02 数据结构 | 3.8 的 list 只是开始——tuple/dict/set、切片、推导式、嵌套结构在这里系统化 |
| ph03 函数与模块 | 3.7 的函数基础进阶：参数语义（4.5 的"传引用"在这里讲全）、作用域、模块拆分 |
| ph04 面向对象 | 4.2 的鸭子类型与"类型属于对象"在 class 里落地 |
| ph05 文件与异常 | 3.4 的 input/print 升级为真实文件 IO，脚本从"玩具"变"工具" |
| ph07 环境与打包 | 4.1 的 venv/pip 概念升级为工程实践（把脚本交给别人用） |
| ph09/ph15 | 基础语法是数据分析（numpy/pandas）与 AI（sklearn）的地基——本路线的终点场景 |

一句话：**Python 路线是"语法最短、生态最深"**——基础阶段只要 400 行就能把所有语法过一遍，真正的学习曲线在之后的标准库与生态；所以本阶段的目标不是"记语法"，而是"能流畅地把想法写成脚本"。

## 6. 代码示例

> **说明**：本节展示完整可运行示例的关键片段，完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.py`，已在本环境用 Python 3.13.12 验证。

### 示例 1：猜测数字游戏

完整文件：`examples/ex01-guess-number.py`

```python
import random

secret = random.randint(1, 100)
attempts = 0

print("猜一个 1-100 之间的数字！")

while True:
    guess = int(input("你的猜测: "))
    attempts += 1

    if guess < secret:
        print("太小了！")
    elif guess > secret:
        print("太大了！")
    else:
        print(f"猜对了！共尝试 {attempts} 次。")
        break
```

### 示例 2：成绩等级判定

完整文件：`examples/ex02-grade-judge.py`

```python
def get_grade(score):
    """根据分数返回等级。"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'

scores = [95, 82, 67, 54, 78, 91]
for i, s in enumerate(scores):
    print(f"学生 {i+1}: 分数={s}, 等级={get_grade(s)}")
```

### 示例 3：词频统计

完整文件：`examples/ex03-word-count.py`

```python
text = "apple banana apple orange banana apple"
words = text.split()

freq = {}
for w in words:
    freq[w] = freq.get(w, 0) + 1    # dict.get 提供默认值

for word, count in sorted(freq.items()):
    print(f"{word}: {count}")
```

### 示例 4：九九乘法表

完整文件：`examples/ex04-multiplication-table.py`

```python
for i in range(1, 10):
    for j in range(1, i + 1):
        print(f"{j}×{i}={i*j:<2}", end="  ")
    print()
```

### 示例 5：简单的命令行工具脚本

完整文件：`examples/ex05-text-stats.py`

```python
import sys

def count_chars(text):
    """统计字符数（含空格）"""
    return len(text)

def count_words(text):
    """统计单词数"""
    return len(text.split())

def count_lines(text):
    """统计行数"""
    return text.count('\n') + 1

if __name__ == "__main__":
    text = sys.stdin.read()
    print(f"字符数: {count_chars(text)}")
    print(f"单词数: {count_words(text)}")
    print(f"行数:   {count_lines(text)}")
```

> **`if __name__ == "__main__"`** 是 Python 的标志性模式：当脚本直接运行（`python script.py`）时 `__name__` 为 `"__main__"`，代码块被执行；当脚本作为模块被导入（`import script`）时则不执行。这让同一个 `.py` 文件既能当脚本运行，又能当库供其他代码导入。

## 7. 总结

### 关键要点

1. **Python 是动态类型语言**：变量不需要声明类型，类型属于对象
2. **缩进是语法的一部分**：4 空格缩进是社区标准，混用 tab/空格会出错
3. **可读性优先**：Python 语法刻意简洁，"做同一件事只有一种显然的方式"
4. **`input()` 返回字符串**：需要数学运算时必须手动类型转换
5. **f-string 是推荐的格式化方式**：`f"{变量}"` 简洁直观（Python 3.6+）
6. **基础阶段就能写出可用脚本**：这是动态语言相对于静态语言的最大优势

### 跨语言对比：基础语法

| 特性 | C/C++/Java | Python |
|------|-----------|--------|
| 类型 | 静态，声明必须指定类型 | 动态，变量名无类型 |
| 代码块 | `{}` 花括号 | 缩进 |
| 语句结束 | `;` 分号 | 换行 |
| 变量声明 | `int x = 5;` | `x = 5` |
| 循环索引 | `for (int i = 0; i < n; i++)` | `for i in range(n)` |
| 字符串格式化 | `printf` / `std::cout` | f-string |
| 空值 | `NULL` / `nullptr` / `null` | `None` |
| 布尔 | `true`/`false` | `True`/`False`（首字母大写） |

### 阶段验收清单

- [ ] 能独立运行 Python 脚本和 REPL
- [ ] 能用条件和循环解决基础问题
- [ ] 能写带有参数的函数
- [ ] 能使用 `list`、`str` 的常用方法
- [ ] 能读和写 f-string 格式化输出

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：成绩等级判断工具——输入成绩输出等级，支持批处理多个成绩。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[数据结构阶段](../ph02-data-structure/02-data-structure.md) — 深入 list、tuple、dict、set，切片、推导式和嵌套数据结构。
