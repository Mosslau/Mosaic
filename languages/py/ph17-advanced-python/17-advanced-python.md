# Python 高级 Python 阶段

> 面向「把 Python 用到炉火纯青」：理解「为什么这样设计」——迭代器与生成器的惰性本质、装饰器与上下文管理器的协议层、描述符与元类如何支撑整个对象模型、GIL 与垃圾回收的机制真相、import 系统与协程原理，以及 C 扩展 / Cython 的性能边界。从「会写、会用」走向「能解释、能选型、能判断是否必要」。

## 1. 概述

Python 高级 Python 阶段的目标是：**理解 Python 底层机制和高级特性**（roadmap 第 17 节目标）。它是 Python 学习路线（ph01~ph16）的「回炉重造」一站：前面每个阶段都在「用 API」，本阶段把使用背后挂着的**协议与机制**逐层拆开——ph02 用过 `for`，这里讲迭代器协议与 `for` 循环的展开；ph03 用过函数与模块，这里讲闭包与装饰器的执行模型、import 的查找与缓存；ph04 用过 `@property` 与 `@classmethod`，这里讲描述符协议（它们不过是描述符的现成实现）与元类；ph05 用过 `with open(...)`，这里讲上下文管理器协议与 `contextlib` 工具箱；ph14 用 async/await 写并发并实测了 GIL 的影响，ph16 部署时把服务并发的答案指向事件循环——本阶段把「协程原理」「GIL 为什么存在」「uvicorn 为什么一个进程能服务上千连接」三个伏笔一次兑现，再补上内存管理（引用计数 + 分代 GC）、import 机制、数据类三选一（dataclass / attrs / pydantic）与 C 扩展 / Cython 的定位。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 迭代与惰性 | 迭代器协议（`__iter__`/`__next__`/`StopIteration`）、`for` 循环展开、生成器（`yield`/`send`/`throw`/`yield from`）、生成器表达式、惰性处理大文件——3.1/3.2 |
| 函数增强 | 闭包与 `nonlocal`、装饰器（`functools.wraps`、带参装饰器、类装饰器）、横切逻辑注入——3.3 |
| 资源与协议 | 上下文管理器协议（`__enter__`/`__exit__`）、`contextlib`（`contextmanager`/`ExitStack`/`suppress`）、事务语义——3.4 |
| 对象模型深层 | 描述符协议与 `property`/`classmethod`/`staticmethod` 的手写实现、`__set_name__`——3.5 |
| 类与实例工厂 | 元类（`type` 的元类本质）、`__init_subclass__` 取舍、注册表模式——3.6 |
| 导入与打包认知 | import 机制（`sys.path`/`sys.modules`/查找器加载器）、相对导入陷阱、`importlib`——3.7 |
| 数据类三选一 | `@dataclass` 机制（代码生成/`field`/`__post_init__`/`frozen`/`slots`）、与 attrs、pydantic 的对比取舍——3.8 |
| 异步原理 | 协程对象与 `await` 挂起、事件循环调度（Task/Future/回调）、`async for`/`async with`、uvicorn 单进程高并发的机制答案——3.9 |
| 性能边界 | GIL 切换时机与影响、free-threaded 实验、引用计数 + 分代 GC 与循环引用、`weakref`、`__slots__`、ctypes/cffi/C 扩展/Cython 定位对比——3.10/第 4 章 |
| 代码层 | 7 个示例（examples/）+ 5 个练习（exercises/）+ 综合项目（project/：流式日志处理器） |

这个阶段只涉及**Python 语言自身的协议、机制与运行时原理**——迭代器/生成器/装饰器/上下文管理器/描述符/元类/import/dataclass/协程原理/GIL/垃圾回收/C 扩展定位，**不涉及并发编程的选型与 API 使用本身（threading/multiprocessing/asyncio 的用法、实测与选型口诀——那是 ph14 并发、并行与异步阶段的内容，本阶段 3.9/4.4 只补「事件循环内部怎么转」的机制层）、Web 框架与接口层（FastAPI 路由/中间件、Pydantic 在 Web 边界的使用与 pydantic-core 的 Rust 校验原理——那是 ph10 Web 后端开发阶段的内容，本阶段 3.8 只做数据类三选一的定位对比）、数据分析与 AI 训练（NumPy/Pandas/PyTorch 与建模评估——ph09 数据分析阶段 / ph15 AI 与机器学习阶段的内容，本阶段不碰数据科学栈，只讲语言机制）和 C 语言的语法与内存细节（ctypes/cffi/C 扩展要求 C 基础——C 语言学习路线另有 languages/c 的完整阶段，本阶段只讲 Python 侧的接口形态与定位对比）**。与 ph14 的边界尤其要划清：ph14 回答「并发怎么写、怎么选」，本阶段回答「await 挂起时事件循环内部发生了什么、GIL 凭什么限制并行、一个进程为什么能服务上千连接」；与 ph16 的边界同理：ph16 用 GIL 结论做部署选型（pre-fork 多进程），本阶段解释这个结论为什么成立。本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

「高级特性」不是一次设计出来的，而是 CPython 三十多年演进中**一层层协议沉淀**的结果。**设计哲学一句话：Python 用「协议（duck typing）优先于继承」组织高级特性——只要对象实现了约定的魔术方法，语言机制就按协议工作，类层级反而是可选的**。

- **迭代与生成（1994-2006）**：`for` 循环从「序列的下标遍历」演进为「任意可迭代对象的协议遍历」。PEP 234（2001，Python 2.2）确立迭代器协议（`__iter__`/`__next__`）；PEP 255（2001，Python 2.2）引入生成器 `yield`——Python 是第一门把「在函数中间暂停」做成一等语法的主流语言；PEP 342（2005，Python 2.5）给生成器加 `send`/`throw`/`close`，让生成器能双向通信；PEP 380（2009，Python 3.3）引入 `yield from` 委托子生成器。
- **函数增强（1998-2009）**：Python 2.2（2001）把函数改为**描述符**（访问时自动绑定 `self`），2.4（2004）加入 `@decorator` 语法（PEP 318）——装饰器最初只是语法糖，却催生了 Flask、pytest、FastAPI 等一大批「声明式框架」，是 Python 生态最强大的约定式扩展点。
- **上下文管理器（2005-2006）**：`with` 语句 PEP 343（2005 年通过，Python 2.5 发布，Guido 亲自设计，源于 `try/finally` 的防遗忘诉求），`contextlib` 随 2.5 一并进入标准库——「资源必释放」从口头纪律变成协议化语法。
- **描述符与元类（2000-2016）**：描述符协议（PEP 252/253，2001，Python 2.2 新式类）是 `property`/`classmethod`/`staticmethod` 与**方法绑定**的共同底座；元类自 Python 1.5 起就是 `type` 的内置能力；Python 3.6（PEP 487）新增 `__init_subclass__` 与 `__set_name__`，把元类最常用的两个场景（子类注册、属性收名）降级为「不需要自定义元类也能做」。
- **数据类（2017-2023）**：PEP 557 的 `@dataclass`（Python 3.7）把「写样板 `__init__`/`__repr__`/`__eq__`」变成注解驱动的代码生成；更早的 attrs（2015 年起，Hynek Schlawack）已用装饰器做了同样的事；pydantic（2017 年 Samuel Colvin 创立，v2 于 2023 年用 Rust 重写核心为 pydantic-core）则把「数据容器」升级为「边界校验 + 序列化 + 模式导出」。
- **异步（2012-2016）**：asyncio 由 Guido 2012 年设计（PEP 3156，Python 3.4），参考 Twisted/Tornado；PEP 492（2015，Python 3.5）引入一等语法 `async`/`await`；PEP 525（Python 3.6）补上异步生成器。事件循环的机制层（本阶段 3.9/4.4）讲的就是这段历史沉淀出的「单线程调度海量 IO」模型。
- **内存与 GIL（1992-2024）**：引用计数是 CPython 从 1.0 就采用的内存管理（对象归零即释放）；循环引用的漏洞用 2000 年加入的分代垃圾回收（`gc` 模块）补上；GIL 由 Guido 1992 年为支持多线程引入（见 4.3 为什么）；2023 年 PEP 703（Sam Gross）的 free-threaded 提案被接受，Python 3.13 首次提供无 GIL 的实验性构建（详见 4.3）。
- **C 扩展形态（1996-2010s）**：C API 扩展模块（Python 1.x 起）、ctypes（Python 2.5，2006，调用现成 C 库的 FFI）、Cython（2007 年开源，Python 超集编译为 C）、cffi（2012 年前后）——四代形态解决同一问题：Python 太慢的部分怎么办。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| PEP 255 生成器 | 2001（2.2） | `yield` 进入语言，函数可暂停/恢复 |
| PEP 234/252 迭代器与描述符 | 2001（2.2） | 迭代器协议、新式类描述符协议（方法绑定底座） |
| PEP 343 `with` 语句 | 2005（2.5） | 上下文管理器协议 + `contextlib` |
| PEP 342 生成器增强 | 2005（2.5） | `send`/`throw`/`close`，生成器双向通信 |
| PEP 380 `yield from` | 2009（3.3） | 子生成器委托，生成器可组合 |
| PEP 3156 asyncio | 2012-2014（3.4） | 事件循环 + 协程进标准库（Guido 设计） |
| PEP 492 async/await | 2015（3.5） | 一等异步语法，协程与生成器分离 |
| PEP 487 `__init_subclass__` | 2016（3.6） | 多数元类场景不再需要自定义元类 |
| PEP 557 `@dataclass` | 2017（3.7） | 注解驱动的数据类代码生成 |
| PEP 703 free-threaded | 2023 提案 / 3.13 实验 | 无 GIL 实验构建；标准构建仍带 GIL |
| pydantic v2 | 2023 | Rust 核心（pydantic-core），校验性能数倍提升 |

本文示例以 **Python 3.13** 为基线（当前 CPython 稳定大版本；3.13 恰好是「带 GIL 的标准构建」与「实验性 free-threaded 构建」并存的版本，讲 GIL 正合适），验证工具链 **Python 3.13.9 + pytest 8 + ruff 0.12**（对齐 ph13/ph16 的工具链基线；代码层依赖 pydantic 2.x 处单独标注）。本阶段的语法与协议（迭代器/描述符/上下文管理器/`yield from`/`__init_subclass__`）是 Python 3.x 时代**最稳定的接口层**，十余年未变；free-threaded 按实验特性简述（4.3），不改变任何面向标准构建的写法。**验证纪律**：examples/exercises/project 全部代码已在 Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 本机实测通过（main 自检与 pytest 断言全绿、ruff check/format 全绿），文件头与 README 标注「已验证」，命令见文件头与各 README；本文内嵌代码为教学骨架或摘录，验证状态以对应文件为准。

## 3. 语法与参数

> 本节内嵌代码块为**教学骨架或摘录**：为聚焦单个知识点做了简化。完整可运行文件与验证命令见第 6 章与 [`examples/`](./examples/)——examples/exercises/project 全部已在 Python 3.13.9 本机实测通过（标注「已验证」，见各文件头）。

### 3.1 迭代器协议：`for` 循环的展开

`for x in xs:` 并不认识「列表」，它只认识**可迭代对象**。可迭代对象 = 能交给 `iter()` 的对象：

```python
# examples/ex01-iterator-generator.py —— 迭代器协议与 for 展开
xs = [10, 20, 30]
it = iter(xs)          # list.__iter__() → 迭代器
print(next(it))        # 10  —— iterator.__next__()
print(next(it))        # 20
```

`for` 循环的完整展开是「显式拿到迭代器 + 反复 next + 捕获结束信号」：

```python
# for x in xs: ... 等价于（教学展开，见 examples/ex01 的 test_for_loop_expansion）
it = iter(xs)                     # 1. 取迭代器
while True:
    try:
        x = next(it)              # 2. 取下一个
    except StopIteration:         # 3. 耗尽 → 结束
        break
    print(x)                      # 4. 循环体
```

三个关键点：

- **协议是「duck typing」**：实现 `__iter__` 返回迭代器即可被 `for` 消费；更古老的对象只实现 `__getitem__(i)`（整数下标），`iter()` 也会从 0 开始逐个尝试直到 `IndexError`（序列协议兜底）。
- **可迭代 ≠ 迭代器**：`list` 有 `__iter__` 没有 `__next__`（可重复遍历）；迭代器有 `__next__`，且 `__iter__` 返回**自己**（`it is iter(it)` 为真）——这让迭代器可被 `for` 连续消费而不会从零开始。
- **迭代器是一次性的**：`next` 推进游标，耗尽后再次 `next` 抛 `StopIteration`。`for` 内部消化了这个信号，裸调 `next` 时容易踩「没捕获 StopIteration」的坑。

**自定义可迭代对象**：实现 `__iter__`（返回迭代器）即可接入全部接受可迭代对象的 API（`list()`/`sum()`/`sorted()`/`for`/推导式/`in`）。标准库 `collections.abc.Iterable` / `Iterator` 提供协议标记与 `isinstance` 判断。**为什么学协议而不是学 API**：协议是 Python 所有「能吃一坨东西」的函数的公共接口——理解了协议，任何对象（数据库游标、socket 流、日志文件）只要实现 `__iter__`/`__next__` 就能被同样对待，这就是**鸭子类型在语言机制层的体现**。

> 阶段内容隔离：`itertools`（`chain`/`islice`/`tee`/`groupby` 等惰性工具）的用法入门在 ph06 标准库阶段，本阶段只补迭代器协议本身与生成器这一「协议的最重要实现」。

### 3.2 生成器：惰性、`send`/`throw`/`yield from`

**生成器函数 = 含 `yield` 的函数**。调用它不执行函数体，而是返回一个**生成器对象**（也是迭代器）；函数体在每次 `next()`/`send()` 时执行到下一个 `yield` 暂停，帧状态（局部变量、执行位置）被完整保存。**必会概念「生成器适合惰性处理大数据」的机制**：值是一次一个生产出来的，内存占用 O(1)，不预先构建整份序列：

```python
# examples/ex01-iterator-generator.py —— 惰性与 send/yield from
def countdown(n):                  # 生成器函数
    while n > 0:
        yield n                    # 暂停点：产出 n，等下一次 next/send
        n -= 1
c = countdown(3)
print(next(c))                     # 3 —— 函数体跑到第一个 yield 暂停
print(list(c))                     # [2, 1] —— 继续消费到 StopIteration

def echo() -> Iterator[str]:           # 双向通信：send 把值送回暂停点
    got = yield "ready"                # 首次 send(None) 启动，yield 表达式求值为 send 的参数
    yield f"got:{got}"

e = echo()
print(next(e))                         # ready（启动协程式交互）
print(e.send("ping"))                  # got:ping —— send 恢复执行并把值赋给 got
```

生成器对象的完整方法面（PEP 342/380 沉淀的协议）：

| 方法 | 作用 | 典型用途 |
|------|------|---------|
| `next(g)`（`g.send(None)`） | 推进到下一个 `yield` | 常规消费 |
| `g.send(v)` | 恢复并把 `v` 作为 `yield` 表达式的值 | 协程式双向通信（流水线） |
| `g.throw(exc)` | 在暂停点抛出异常 | 向生成器注入错误/终止条件 |
| `g.close()` | 在暂停点抛 `GeneratorExit` | 提前释放（for 中途 break 时解释器自动调） |

**`yield from`（PEP 380）** 把「委托给子生成器」写成一等语法：`yield from subgen` 自动转发 `send`/`throw`/`close`，并让子生成器的 `return 值` 成为整个表达式的结果（值藏在 `StopIteration.value` 里，Python 3.3 起 `return x` 在生成器内合法）：

```python
def sub():
    total = yield from countdown(3)   # 委托：countdown 的产出直接透传
    return total                      # 子生成器的"返回值"

def wrapper():
    got = yield from sub()            # 链式委托
    return got
```

手动展开 `yield from` 需要自己写内层 `for` + 转发异常 + 取返回值，极易错——这正是「语法糖封装了正确性」的范例。**生成器表达式** `(x * x for x in range(10_000_000))` 是生成器函数的紧凑形态（`sum`/`any`/`max` 等直接吃，避免构建中间列表——ph06 已见，这里补一句机制：它和显式 `yield` 的函数体编译产物等价）。**陷阱提醒**：生成器只能消费一次；「看起来像列表」的 `in`/`len()`/下标操作对生成器不可用；忘记消费完就丢对象时，`GeneratorExit` 会在 GC 时触发（3.4 的 `contextlib.closing` 与此相关）。

> **注意**：生成器对象在 Python 3.5 之后与协程分道扬镳——`yield` 生成器仍叫生成器，`async def` 产出的是**原生协程对象**（3.9 展开）。PEP 342 的 `send` 当年为「生成器式协程」铺路，3.9 的协程原理要从这里理解历史脉络。

### 3.3 装饰器：闭包、`wraps` 与横切逻辑

**装饰器 = 接收函数并返回函数的可调用对象**，`@d` 是 `f = d(f)` 的语法糖。它之所以在 Python 里特别强大，是因为**函数是一等对象**：函数可以作为参数、返回值、被赋值——装饰器就是这套能力的「定义期钩子」，在函数创建的那一刻注入横切逻辑（计时、日志、缓存、重试、鉴权……）。**必会概念「装饰器适合横切逻辑」**：横切 = 与业务正交、散落在每个函数里会重复的代码（先计时、再调业务、后记日志）。

**闭包是装饰器的底座**：内层函数引用外层函数的变量，外层函数返回后这些变量仍被捕获（编译成 cell 对象而非随栈消失）。没有闭包，装饰器的 `wrapper` 就无法「记住」被装饰的函数与参数。

```python
# examples/ex02-decorators-advanced.py —— 闭包与 wraps
import functools
import time

def timer(func):
    @functools.wraps(func)                    # 把 __name__/__doc__ 等拷给 wrapper
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"{func.__name__} took {time.perf_counter() - start:.4f}s")
    return wrapper

@timer
def slow_add(a: int, b: int) -> int:
    """两数相加（计时装饰器演示）。"""
    time.sleep(0.001)
    return a + b
```

**`functools.wraps` 为什么必须**：没有它，`slow.__name__` 变成 `wrapper`、`help(slow)` 显示的是 wrapper 的文档——调试与工具链（pytest、FastAPI 的路由注册依赖函数名）全被污染。`wraps` 本质是 `update_wrapper`：拷贝 `__module__`/`__name__`/`__qualname__`/`__doc__`/`__dict__`，并记录 `__wrapped__`（`inspect.unwrap` 可穿过装饰器看原函数）。

**带参装饰器是三层函数**：`@retry(times=3)` 先执行 `retry(times=3)` 得到真正的装饰器，再应用它：

```python
def retry(times: int = 3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == times - 1:
                        raise                      # 最后一次重试仍失败 → 原样抛出
        return wrapper
    return decorator
```

**装饰器叠加从下往上应用**：`@a` 在 `@b` 之上时，`f = a(b(f))`——外层装饰器看到的是内层装饰器处理后的函数。日志与计时叠加时，执行顺序是「a 包 b 包 f」：进入 a.wrapper → 进入 b.wrapper → 执行 f。

**类装饰器与可调用对象装饰器**：类实现 `__call__` 即可当装饰器用，且能保存状态（计数、注册表）；装饰器也可以直接装饰**类**（`@dataclass`、`@functools.total_ordering` 都是装饰类的例子）——见 3.6 的注册表场景。标准库的装饰器家族：`functools.lru_cache`/`cache`（记忆化）、`singledispatch`（按首参类型分派）、`functools.partial`（预填参数，非装饰器但常与装饰器配合）、`contextlib.contextmanager`（3.4）。

> **注意**：装饰器在 import 时（定义期）执行一次——「装饰器里做重活」会拖慢模块导入；被装饰函数的签名在工具面前仍是 `(*args, **kwargs)`（除非用 `functools.wraps` 或 `__signature__` 矫正），这是 FastAPI 用 `inspect.signature` 读参数的前提——本阶段只需理解，Web 侧细节属 ph10。

### 3.4 上下文管理器：`with` 的协议与 `contextlib`

**`with` 语句 = 资源获取/释放的协议化**。`with expr as x:` 等价于「调用 `expr.__enter__()` 得到 x 绑定；离开块时无论如何调用 `expr.__exit__(exc_type, exc_val, exc_tb)`」。协议只认这两个方法，不认类层级——任何对象实现它们就能被 `with` 使用：

```python
# examples/ex03-context-managers.py —— 协议与 contextlib
class ManagedFile:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        self.f = open(self.path)
        return self.f                      # as 绑定的是 __enter__ 的返回值
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.f.close()
        return False                       # False：异常继续传播；True：吞掉异常
```

`__exit__` 的四个参数与两个返回值语义是本协议的精华：

| 情况 | 参数 | 返回值语义 |
|------|------|-----------|
| 块正常结束 | 三个都是 `None` | `False` 即可 |
| 块内抛异常 | 异常类型/实例/回溯 | 返回 `True` → 吞掉异常（块外看不到）；`False` → 传播 |
| `__exit__` 自己抛异常 | —— | 新异常**替换**原异常（`raise ... from` 链接保留因果） |

**经典工程语义：事务**——`__enter__` 开事务，`__exit__` 里看 `exc_type is None` 决定 commit 还是 rollback（python-patterns L3 的 `DatabaseTransaction` 即此形态，exercises 练习 3 让你自己写）。

**`contextlib` 工具箱**（本阶段必掌握的一半价值）：

- `@contextmanager`：把生成器函数变成上下文管理器——`yield` 之前是 `__enter__`，之后是 `__exit__`；块内异常会被**抛回 yield 处**（所以用 `try/except` 包住 yield 可以决定吞还是抛）。这是「写类实现协议」的 80% 场景替代品。
- `ExitStack`：动态压入/弹出任意多个上下文管理器（`cm = ExitStack(); cm.enter_context(...)`），`with ExitStack() as cm:` 结束时按后进先出全部退出——连接池、动态依赖清理的标准答案。
- `suppress(*excs)`：显式吞掉指定异常（替代裸 `except: pass`）。
- `closing(obj)`：退出时调 `obj.close()`；`nullcontext()`：占位（参数化测试里 `with maybe_cm or nullcontext():`）。
- `redirect_stdout`/`redirect_stderr`：块内捕获打印输出。

> 阶段内容隔离：`async with`/`@asynccontextmanager` 是上下文管理器协议在事件循环里的延伸，用法层面属 ph14 并发、并行与异步阶段（FastAPI lifespan 已用过）；本阶段 3.9 只从机制上说明 `__aenter__`/`__aexit__` 不过是「挂起版」的同构协议。

### 3.5 描述符：`property`/`classmethod` 的底层

**描述符 = 实现了 `__get__`（可加 `__set__`/`__delete__`）的类属性对象**。访问 `obj.attr` 时，如果 `attr` 在**类**上找到的是描述符，Python 就调用它的协议方法而不是直接返回值。整条属性查找链（ph04 的 4.1 讲过雏形，这里补上描述符这一环）：

```text
obj.attr 查找顺序（data descriptor 优先于实例字典）：
1. type(obj) 的 MRO 上找 attr
2. 找到的是 data descriptor（有 __set__ 或 __delete__）→ 调用 __get__(obj, type(obj))
3. 实例 __dict__ 里有 attr → 直接返回（非 data descriptor 挡不住这一层）
4. 找到的是非 data descriptor（只有 __get__）→ 调用 __get__(obj, type(obj))
5. 都没有 → AttributeError
```

这一条规则解释了 Python 里大量「怪现象」：

- **方法为什么自动带上 `self`**：函数本身就是非 data 描述符（函数对象实现 `__get__`）。`obj.method` 走第 4 步，`function.__get__(obj, type)` 返回绑定了 `obj` 的 MethodType；`Class.method` 则因为 `obj=None` 返回原函数。**实例属性同名时能遮蔽方法**（第 3 步先于第 4 步）——`obj.method = lambda: 1` 会让方法调用行为改变，这就是非 data 描述符与实例字典的优先级设计。
- **`@property` 是 data 描述符**：`property(fget, fset, fdel, doc)` 在 C 层实现 `__get__`/`__set__`/`__delete__`——它抢在实例字典之前（第 2 步），所以「赋值给 property 会走 setter 而不是在实例字典里新建同名属性」。**用纯 Python 手写一个极简 property** 是理解本节的标志性练习：

```python
# examples/ex04-descriptor-metaclass.py —— 手写 property 等价物
class my_property:
    def __init__(self, fget=None, fset=None):
        self.fget, self.fset = fget, fset
    def setter(self, fset):                    # @x.setter 的语法糖
        self.fset = fset
        return self
    def __get__(self, obj, objtype=None):     # data descriptor：先于实例字典
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)
    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(obj, value)
```

- **`@classmethod` 是非 data 描述符**：`__get__` 把**类**（而非实例）作为第一个参数绑定；`@staticmethod` 是「剥掉描述符」的包装——函数本身是描述符，不加 staticmethod 会被绑定，包一层后 `__get__` 直接返回原函数。三者对比：

| 装饰器 | 描述符类型 | `obj.x` 拿到 | `Cls.x` 拿到 |
|--------|-----------|--------------|--------------|
| 裸方法 | 非 data | 绑实例的 MethodType（`self` 注入） | 原函数（`self` 缺失） |
| `@staticmethod` | 非 data（透传包装） | 原函数 | 原函数 |
| `@classmethod` | 非 data | 绑类的 bound method（`cls` 注入） | 绑类的 bound method |
| `@property` | data | `fget(obj)` 的返回值 | property 对象本身 |

- **`__set_name__(self, owner, name)`**（3.6+）：描述符被赋给类时自动收到「所属类 + 属性名」——描述符不再需要靠约定猜自己的名字，是类型标注/ORM 字段（如 SQLAlchemy 的 `Column`）内部的关键钩子。

**必会概念「元类和描述符要谨慎使用」的一半**：描述符是语言底层能力，滥用（动不动自定义描述符）会让属性访问行为难预测、调试困难——先想 `property`/`__set_name__`/`__init_subclass__` 能否满足，最后才考虑自己写描述符。

### 3.6 元类与 `__init_subclass__`：造类的类

**类也是对象，类是 `type` 的实例**（ph04 4.1 已立此认知）。元类 = 实例是类的类：`class` 语句执行时，Python 调用元类（默认 `type`）的 `__new__` 创建类对象、`__init__` 初始化它。自定义元类 = 继承 `type` 并覆写这些方法：

```python
# examples/ex04-descriptor-metaclass.py —— 元类与 __init_subclass__
class UpperMeta(type):
    def __new__(mcls, name, bases, namespace, **kw):
        cleaned = {k: (v.upper() if isinstance(v, str) else v)
                   for k, v in namespace.items() if not k.startswith("__")}
        return super().__new__(mcls, name, bases, cleaned, **kw)

class Greeting(metaclass=UpperMeta):   # class 语句 → UpperMeta("Greeting", (), {...})
    hello = "hi"                       # 定义期即被改写
print(Greeting.hello)                  # HI
```

**元类的三个常用触发点**（其余场景几乎都能用更轻的手段替代）：

| 需求 | 经典做法 | 更轻的替代 |
|------|---------|-----------|
| 子类自动注册（插件/命令表/ORM 模型表） | 元类在类创建时把子类记进注册表 | `__init_subclass__`（3.6+） |
| 类体校验/改写（字段必须大写、禁止某属性） | 元类 `__new__` 扫描 namespace | 类装饰器 |
| 改变实例创建流程（单例/池化） | 元类覆写 `__call__` | 覆写 `__new__` 或工厂函数 |

**`__init_subclass__` 是「元类 90% 场景」的现代替代**（PEP 487）：父类定义它，任何子类创建后自动被调用，无需自定义元类。注册表模式因此从「元类必修课」降级为「两行代码」：

```python
class PluginBase:
    registry: dict[str, type] = {}
    def __init_subclass__(cls, **kwargs):      # 每个直接子类创建时自动调用
        super().__init_subclass__(**kwargs)
        PluginBase.registry[cls.__name__] = cls

class LogPlugin(PluginBase): ...                # 定义即注册
class MetricsPlugin(PluginBase): ...
print(sorted(PluginBase.registry))              # ['LogPlugin', 'MetricsPlugin']
```

**取舍原则（必会概念「元类要谨慎使用」的机制解释）**：元类在**每个类定义**时都插一脚，隐式改变所有子类行为——可读性、工具（类型检查）都受损，多继承下元类冲突直接报错。判据一句话：**「我要在类创建后做一件事」→ 先试 `__init_subclass__`/`__set_name__`/类装饰器；只有「我要改变类创建本身的流程或所有类共享的机制」才上元类**（SQLAlchemy/Django ORM 是「真需要」的教科书案例——它们用元类把类体里的声明变成映射结构）。

### 3.7 import 机制：`sys.path`、模块缓存与相对导入陷阱

**`import` 是一个运行时操作，不是编译期符号解析**——这与其他静态语言（Java/C++ 的 import/include 在编译期）截然不同，是理解 Python 工程行为的钥匙。`import spam` 的执行链：**查找 → 加载 → 缓存**：

```text
import spam
  │ 1. sys.modules 里有 "spam"？── 有 ──▶ 直接用（幂等：只执行一次模块体）
  │ 2. 没有 → 在 sys.path 里找（spam.py / spam/__init__.py / .so / .pyc）
  │ 3. 找到 → 编译（首次）→ 执行模块体 → 建模块对象
  │ 4. 存入 sys.modules["spam"]，绑定到当前命名空间
```

- **`sys.path` 是搜索清单**：按顺序为——脚本所在目录（或交互/`-c` 时的当前目录、`-m` 时的当前目录）、`PYTHONPATH` 环境变量、标准库、site-packages。**同名模块谁在前谁生效**——「本目录放了个 `requests.py` 就再也 import 不到真 requests」是经典事故。
- **`sys.modules` 是缓存字典**：删了它再 import 会重新执行模块体；`importlib.reload(m)` 强制重执行（调试用）。**循环导入事故**的本质：A import B 时 B 又 import A，而 A 只执行到一半（对象尚未定义）——B 拿到的是「半成品模块」，用 `A.x` 时 `x` 还没建出来就 AttributeError。解法：把共享定义下沉到第三个模块、延迟导入（函数内 import）、或只在 `__main__` 边界导入。
- **`from spam import egg` 也会执行整个 spam 模块体**——「只导入一个名字」不省执行开销，省的是命名空间污染。
- **相对导入的陷阱**：包内 `.` 开头的导入（`from . import sibling`、`from ..pkg import x`）只能在**作为包的一部分被导入**时工作（`python -m pkg.mod`）；直接 `python pkg/mod.py` 时 `__package__` 为空，相对导入直接 `ImportError: attempted relative import with no known parent package`——这是「脚本能跑、做成包报错」的头号原因。规则：**文件要么是脚本（顶层绝对导入），要么是包成员（-m 运行/相对导入），别混**。
- **`if __name__ == "__main__":` 的机制**：`__name__` 在「被直接运行」时是 `"__main__"`、被 import 时是模块全名——这正是脚本/模块双形态分岔的执行点（ph03 已用，这里补机制：导入执行会重跑顶层代码，守卫避免副作用在导入时触发；ph14 的 spawn 多进程也依赖它）。

**字节码缓存**：模块首次编译后源码连同编译元信息写进 `__pycache__/spam.cpython-313.pyc`，再次导入时按源码 mtime/size 校验，命中则跳过编译直接加载——`.pyc` 是缓存不是分发物。

### 3.8 数据类三选一：dataclass / attrs / pydantic

ph13 已把 `@dataclass` 当工程工具用过（自动生成 `__init__`/`__repr__`/`__eq__`）；ph10 已把 pydantic 用在 Web 边界并讲过 v2 的 Rust 核心。本阶段补**机制与取舍**——三者回答同一个问题「我要一个数据容器」，但承诺不同：

**`@dataclass` 的机制：类装饰器做代码生成**。`@dataclass` 在类定义完成后，读类注解（`__annotations__`），按字段顺序生成 `__init__`（无默认值字段在前）、`__repr__`、`__eq__`（比较是按字段元组的相等）、`__hash__`（`eq=True` 且 `frozen=True` 时按字段生成；否则置 `None` 使实例不可哈希——与普通类一致）、`__post_init__` 钩子（在 `__init__` 末尾调用，做校验/派生字段）。它是**编译期等价替换**——`@dataclass class P: x: int` 生成的 `__init__` 与手写 `def __init__(self, x): self.x = x` 无异，不引入运行期魔法：

```python
# examples/ex06-dataclass-pydantic.py —— dataclass 机制与三选一
from dataclasses import dataclass, field, asdict

@dataclass(frozen=True)                      # 冻结：实例不可变（hash 可用）
class Point:
    x: float
    y: float

@dataclass
class Record:
    name: str
    tags: list[str] = field(default_factory=list)   # 可变默认值必须走 factory
    seq: int = field(init=False)                    # 不在 __init__ 参数里
    def __post_init__(self):
        self.seq = self.name.lower()                # 生成 __init__ 后自动跑的钩子
```

`field()` 的关键参数：`default_factory`（可变默认值的正确写法——直接 `= []` 会让所有实例共享同一个列表，ph04 的可变默认参数陷阱在此重现）、`init=False`、`repr=False`、`compare=False`。Python 3.10+ 还有 `kw_only=True`（关键字构造）与 `slots=True`（生成 `__slots__`，见 4.2）。

**三选一判据**（roadmap 的 dataclass/pydantic 知识点落点）：

| 维度 | `@dataclass`（stdlib） | attrs | pydantic（v2） |
|------|------------------------|-------|----------------|
| 出身 | PEP 557，3.7 进标准库 | 2015 年第三方库（先于 dataclass，后者的功能灵感来源） | 2017 年第三方库，面向边界校验 |
| 运行期校验/类型转换 | 无（类型注解只是声明，不检查） | 可选（`@attr.s` + validators/converters） | 有（构造时强校验 + 类型转换，失败抛 ValidationError） |
| 序列化/模式 | 无（`asdict` 仅递归转 dict） | 部分 | `model_dump_json`/schema 导出，一等公民 |
| 性能 | 生成原生 Python 代码 | 类似 dataclass | 校验在 Rust 核心（pydantic-core） |
| 典型场景 | 进程内数据容器/领域对象 | 需要 dataclass+ 的校验但不想上 pydantic | API/配置/外部数据边界（ph10 已深用） |

一句话选型：**进程内部、无外部输入的纯数据容器 → dataclass（标准库零依赖）；需要在「信任边界」上校验外部数据（HTTP 请求、配置文件、DB 行）→ pydantic（fail-fast + 自动类型转换 + JSON 直出）；需要介于两者之间的运行期校验又不想背 Rust 核心依赖 → attrs**。dataclass 与 pydantic 还能互相转换：`TypeAdapter`/`model_validate` 可直接消费 dataclass 结构——「内部用 dataclass、边界套 pydantic」是常见组合。

> 阶段内容隔离：pydantic 的 Web 用法（FastAPI 依赖注入、OpenAPI 生成）与 pydantic-core 校验原理在 ph10 Web 后端开发阶段已展开，本阶段不重复，只把它放进「数据容器选型」坐标系里对齐定位。

### 3.9 协程原理：async/await 与事件循环怎么转

ph14 用 `async def`/`await` 写出了并发并实测了「await 让出、阻塞抹平并发」；ph16 把它部署成了 uvicorn 服务。本阶段回答机制：**`async def` 调用的返回值是什么？`await` 到底做了什么？事件循环凭什么用一个线程服务上千连接？**

**协程对象与生成器同源而异途**：Python 3.5（PEP 492）前，协程就是生成器（用 `send` 手动喂，`asyncio` 1.x 的 `@asyncio.coroutine` 即此形态）；3.5 起 `async def` 产出**原生协程对象**——调用 `async def f()` 只是创建对象，**函数体一行都不跑**（与生成器同款惰性）；协程对象内部编译产物与生成器同构（一个可暂停的帧），但协议分家：协程不是迭代器，只能被 `await` 驱动。

**`await` 是挂起点**：`await x` 要求 `x` 是 awaitable（协程对象、Task/Future、或实现了 `__await__` 的对象）。执行到 `await` 时，当前协程把控制权**让回给驱动它的调度器**，自身挂起并注册「x 完成时叫我」；`x` 完成后，调度器把结果（或异常）送回来，协程从挂起点继续。**没有 await 的协程函数体 = 普通函数**——`asyncio.run(f())` 里如果 `f` 内部没有任何 await，它会一口气跑完，与同步函数无异（ph14 的阻塞反例正是「await 里放了个不让出的阻塞调用」）。

**事件循环 = 就绪队列调度器 + IO 事件通知**。`asyncio.run(main())` 做的事：建一个 `SelectorEventLoop`（Linux 用 epoll、macOS/Windows 用 kqueue 等，`selectors` 模块封装）→ 把 `main()` 包成 **Task**（Task = 协程 + 状态 + Future 结果槽）→ 开始驱动：

```text
事件循环主循环（伪代码展开）
while 还有活要干:
    for 每个就绪 Task:                 # 1. 驱动协程步进
        task.__step(): coro.send(None) #    跑协程直到下一个 await
            ├─ await 的东西未完成 → 协程挂起，注册 done_callback
            └─ await 的东西已完成   → send(结果)，继续跑
    selector.select(timeout)          # 2. 等 IO 事件（没有就绪任务时阻塞在这）
    for 每个就绪 fd:                  # 3. 数据来了 → 把 Future 置为完成
        回调 → 唤醒挂起的 Task → 回到 1
```

Task 的机制核心：协程每次 `await` 挂起后，控制权回到循环；IO 到达时循环把 Future 置完成、触发回调，回调调用 `task.__step()`，`__step` 用 `coro.send(result)` 恢复协程。**`asyncio.sleep(0)` 为什么能让出**：它创建一个「定时完成」的 Future 并立即 await——任务挂起一轮，循环就有机会跑其他任务。

**一个进程服务上千连接的答案（兑现 ph16 的预告）**：连接数不占线程——每个连接在应用侧只是「一两个协程对象 + 一个 socket」，协程的暂停态是一个栈帧（几十字节到 KB 级）；切换是用户态 `send`/恢复，微秒级，而线程切换要内核参与（上下文切换 + 每线程约 8MB 栈的虚拟内存）。等待 IO 时线程会阻塞占资源，协程只留下一个「fd 就绪了叫我」的注册。于是**千级并发连接 = 千个挂起协程排队在同一个事件循环上**，一个进程即可扛住——这就是 uvicorn（ASGI 服务器，事件循环上跑 FastAPI 应用）单进程高并发的机制答案；横向再加 `--workers N` 或容器副本（ph16）是为多核 CPU 与容灾，不是为连接容量。

**异步协议族**（机制同构、语义挂起）：`async with` 走 `__aenter__`/`__aexit__`、`async for` 走 `__aiter__`/`__anext__`（异步生成器用 `yield` 于 `async def` 内，PEP 525）——每个都是同步协议在「await 版」的镜像。

> 阶段内容隔离：async/await 的**用法**（create_task/gather/锁/信号量/线程池桥接）与选型实测在 ph14 并发、并行与异步阶段；本阶段只讲「挂起与调度内部发生了什么」。uvloop 是 uvicorn 可选的替代事件循环（用 Cython + libuv 实现），机制模型与本阶段所述一致，其 Cython 身份见 3.10 的定位对比，不另展开。

### 3.10 C 扩展与 Cython：性能边界的四代形态

**为什么需要碰 C**：Python 的解释执行 + 动态派发决定了纯 Python 数值/热点循环比 C 慢一两个数量级。加速路径有**四代形态**，成本与收益递增：

| 形态 | 机制 | 是否需要编译 | 开发成本 | 典型场景 |
|------|------|-------------|---------|---------|
| `ctypes`（FFI） | 运行期加载 `.so`/`.dylib`，声明函数签名后调用 | 否（只调现成库） | 低 | 调系统库/第三方 C 库（libc、libm、SQLite 等） |
| `cffi` | C 声明 + ABI/API 模式绑定 | 可选 | 中 | 比 ctypes 快、绑定更规范的 FFI |
| C API 扩展模块 | 用 Python/C API（`PyObject` 等）写 C，编译为扩展模块 | 是 | 高 | 完全控制、给 Python 写真正的模块（标准库大量如此） |
| Cython | Python 超集（`.pyx`），可选加 C 类型标注，编译为 C 再编成扩展 | 是 | 中 | 渐进加速既有 Python 代码（uvloop 即用 Cython 实现） |

```python
# examples/ex07-import-gc-memory.py —— ctypes 调 libc 的最小形态
import ctypes
libc = ctypes.CDLL(None)                    # None = 当前进程已加载的库（含 libc）
libc.strlen.argtypes = [ctypes.c_char_p]
libc.strlen.restype = ctypes.c_size_t
print(libc.strlen(b"hello"))                # 5 —— 纯 C 调用，不经 Python 逐字符解释
```

```cython
# Cython 教学片段（.pyx 语法展示，仅示范构建命令；无对应 examples 文件 —— 未在本环境验证，需 pip install cython 后构建）
# 文件: sum_range.pyx —— 加 C 类型标注后，循环编译为 C 的 for
def sum_range(long n):
    cdef long total = 0
    cdef long i
    for i in range(n):
        total += i
    return total
# 构建: pip install cython && python3 -c "from setuptools import setup; from Cython.Build import cythonize; setup(ext_modules=cythonize('sum_range.pyx'))"
```

**定位一句话**：ctypes/cffi 是「**调用** C」的胶水，C 扩展是「**写** Python 模块给 C 代码」，Cython 是「把 Python 代码**渐进变快**」的中间带——三者共同点：性能临界区才值得，且都要对 GIL 有概念（C 代码可主动释放 GIL 让多线程真并行，4.3 收尾）。

> 阶段内容隔离：C 语言的语法、指针与内存模型是 languages/c 学习路线（c.md 的 ph01~phNN）的内容，本阶段只给出 Python 侧的接口形态与选型坐标，不展开 C 语言本身。

## 4. 底层原理

### 4.1 CPython 对象模型：一切皆 PyObject

CPython 里每个对象的内存头是一个 `PyObject`：**引用计数 `ob_refcnt` + 类型指针 `ob_type`**（可变对象再加 `ob_size`）。这是理解内存管理（4.2）与 GIL（4.3）的地基：

```text
PyObject 内存头（每个对象都带）
┌──────────────────────────┐
│ ob_refcnt（引用计数）       │ ← 4.2 回收的依据；4.3 GIL 要保护的头号字段
│ ob_type（指向类型对象）     │ ← 动态派发：type(obj).method(...)
│ ...对象特有数据...          │
└──────────────────────────┘
```

三个「身份」相关的语言行为都从这来：

- **`is` vs `==`**：`is` 比较对象**地址**（同一对象），`==` 调 `__eq__` 比较**值**。`x is None` / `x is True` 是身份比较的正确用法（None/True 是单例）。
- **`id()` 返回对象地址**（CPython 实现细节）：`id(a) == id(b)` 等价于 `a is b`；对象被回收后地址可被复用——不要跨生命周期保存 `id` 作身份。
- **小对象缓存/驻留**：CPython 预分配了 `-5..256` 的小整数单例（`257 is 257` 可能为 False 而 `5 is 5` 恒 True）；部分字符串（标识符、字面量）被 intern。这是「同一值却是不同对象」的经典面试题的答案，也是**身份比较只用于单例**（None/True/False）的原因——值比较永远走 `==`。

`__slots__` 是对象模型上的工程开关：声明 `__slots__ = ("x", "y")` 后实例不再建 `__dict__`（省下每实例一个 dict，约 100+ 字节）与 `__weakref__`（需要 weakref 支持时显式加），属性访问走固定槽位更快。**只对「百万级实例」的纯数据类值得**（配合 `@dataclass(slots=True)`，3.8）；代价是失去动态加属性与工具链兼容性。

### 4.2 引用计数、分代 GC 与循环引用

**CPython 主回收机制是引用计数**（非标记-清除扫全堆）：`obj = ...` 使 `ob_refcnt += 1`，离开作用域/被覆盖/`del` 使计数减一；归零立即回收内存并调 `__del__`（若定义）。**优点：及时（对象一死就回收，无需停顿扫描）、确定性（与语言级 try/finally 同节奏）**；**缺点：循环引用计数永不归零**——两个对象互相引用、但外界无人引用它们时，计数各为 1，永不释放：

```python
# examples/ex07-import-gc-memory.py —— 循环引用与 gc
class Node:
    def __init__(self):
        self.peer = None

a, b = Node(), Node()
a.peer, b.peer = b, a          # 互相引用，外部引用删除后计数不会归零
import gc
print(gc.is_tracked(a))        # True —— 容器对象默认被 GC 追踪
```

**分代垃圾回收补循环引用的漏**（2000 年起随 CPython 发布，`gc` 模块）：GC 只追踪「可能成环」的容器对象（list/dict/自定义类实例等；int/str 等原子对象不追踪），把追踪对象分**三代**：新对象进第 0 代，每代满阈值（默认 `(700, 10, 10)`）触发一次该代回收，幸存者晋升上一代。回收 = 找到「只被环内互相引用」的对象组，把它们**当作没引用**清掉引用计数（`gc.collect()` 手动触发全量回收并返回回收数）。为什么分代：绝大多数对象朝生暮死，只扫年轻代成本低——**GC 开销与存活对象成正比，与分配总量基本无关**。

两个工程推论：**① 带 `__del__` 的对象进循环会麻烦**（PEP 442，3.4 起 CPython 用「临时复活再清」安全处理终结器，对象仍能被回收，但 `__del__` 的调用时机不可依赖——资源清理请用上下文管理器/`weakref.finalize`，别赌 `__del__`）；**② 需要「缓存大对象但不想阻止回收」时用 `weakref`**（弱引用不增加引用计数；`weakref.ref`/`WeakValueDictionary` 是缓存的标准答案——对象被强引用清空后弱引用自动失效并触发回调）。`sys.getrefcount` 可查计数（自身也算一次）、`gc.get_objects` 可遍历全部追踪对象（内存泄漏排查利器）。

**内存分配的另一半**：对象数据不在每次 `malloc` 上——CPython 用小对象分配器（pymalloc）：<512 字节的对象从预分配的 arena/pool 里取，复用率高、碎片少；大对象才走系统 `malloc`。这就是「百万小对象也能跑」的底气。

### 4.3 GIL：为什么存在、何时切换、free-threaded 是什么

**为什么存在（兑现 ph14/ph16 的预告）**：CPython 靠引用计数管内存（4.2），而引用计数是**解释器全局共享的可变状态**——两个线程同时给同一个对象增减计数就会竞态（计数错乱 → 对象被提前回收或永不被回收，双双崩溃）。给每个对象/每个全局状态加**细粒度锁**是正路但极贵（1990 年代的自由线程尝试测得性能大幅下降）；Guido 1992 年的工程决策是**一把进程级大锁 GIL**：同一时刻只允许一个线程执行 Python 字节码，引用计数天然安全——用「放弃多核并行」换来「实现简单 + 单线程性能好」。

**切换时机**（ph14 实测现象背后的机制）：GIL 不是「线程永远占着」。CPython 主循环每个字节码指令间隔检查一次是否该让出，Python 3.2 起改为**时间片制**：线程执行约 `sys.getswitchinterval()`（默认 **5ms**）后主动让出 GIL，等被唤醒的线程轮替；此外**所有可能阻塞的调用（IO 读写、sleep、锁等待）执行前显式释放 GIL**——这是「IO 密集线程池能加速」的机制根源。切换语义在 3.10+ 因 PEP 684（per-interpreter GIL）与 3.12 后的优化有所演进，但「计算占锁、等待放锁」的心智不变。`sys.setswitchinterval` 可调（诊断用，别乱调）。

**影响全景**（衔接 ph14 的实测与 ph16 的部署结论）：

| 场景 | GIL 影响 | 结论（与既有阶段的呼应） |
|------|---------|------------------------|
| CPU 密集多线程 | 线程轮流抢锁执行，无并行（ph14 ex02 实测 ≈ 串行） | CPU 密集用 multiprocessing——ph14 选型口诀 |
| IO 密集多线程 | 等待时释放 GIL，等待可重叠（ph14 实测 6.7 倍加速） | IO 密集用线程/异步——ph14 |
| 单进程多核利用 | 单进程吃不满多核 | ph16 的 Gunicorn pre-fork / `--workers` 多进程模型——「GIL 逼出多进程」 |
| C 扩展/重型库 | C 代码可显式释放 GIL（`Py_BEGIN_ALLOW_THREADS`）再算，算完重新抢 | NumPy 等向量化运算期间放锁——「Python 慢的部分交给会放锁的 C」 |
| 多线程共享可变状态 | GIL 不保证复合操作原子（ph14 3.2 的注意块） | 共享状态仍需显式锁 |

**free-threaded（PEP 703，3.13 实验）**：2023 年 Sam Gross 的提案被接受——用「延迟引用计数（deferred refcounting）+ biased counting + 细粒度锁」重做对象生命周期，摘掉 GIL 让纯 Python 多线程也能用多核；Python 3.13 起提供 `--disable-gil` 的实验性构建（官方预编译包标记 `-t`，如 `python3.13t`）。**为什么只能渐进**：整个 C 生态假设「有 GIL 就不用给解释器状态加锁」——free-threaded 下第三方 C 扩展必须逐个适配（显式加锁），适配完成的扩展才敢在无 GIL 构建里运行，否则解释器会拒载不安全的扩展。**现状与写法**：标准构建仍带 GIL，本阶段全部结论与代码都以标准构建为准；free-threaded 是「多核 Python 的未来方向」，面向它的迁移按官方文档逐步进行（3.14 及以后的正式化节奏以 PEP 703 与官方发布说明为准）。判断一句话：**写代码仍按「有 GIL」推理（默认安全、加锁不亏）；评估瓶颈时知道「摘 GIL」是正在路上的另一条出路**。

### 4.4 执行模型：源码 → 字节码 → 帧

CPython 是**字节码解释器**：源码先编译为 code object（内含字节码），运行时由主循环（CEVAL）逐条解释执行：

```text
.py 源码 ──编译──▶ AST ──▶ code object（字节码 + 常量 + 变量名表）
                          │
运行时                    ▼
        Python 帧（frame：局部变量 + 执行位置 + 所属模块/函数）
        每函数调用压一个新帧 ──▶ 主循环逐条执行字节码（遇阻塞检查 GIL）
```

- **帧是「暂停单位」的物理载体**：生成器/协程能暂停恢复，是因为帧（连同局部变量、执行位置）被保存而不是随调用返回销毁——`yield`/`await` 只是「保存当前帧 + 返回控制权」，恢复时把帧翻出来继续。这统一了 3.1/3.2/3.9 的所有「暂停」。
- **闭包与 cell**：内层函数引用的外层变量编译为 cell 对象，帧退出后 cell 存活——闭包的本质（3.3）。
- **字节码可查**：`dis.dis(f)` 看函数编译产物、`f.__code__.co_varnames` 看局部变量表、`sys.settrace`/`sys.setprofile` 是帧级钩子（调试器/覆盖率工具的地基）。性能感性认知：一条 Python 语句 = 多条字节码 = 多次动态派发——这量化了 3.10 的「为什么慢、为什么 C 扩展快」。

## 5. 使用场景

| 场景 | 用什么 | 理由 |
|------|--------|------|
| 处理超大文件/无限流（日志、管道） | 生成器逐行/逐块产出 | 内存 O(1)，可无限；project/ 的流式日志处理器即此（呼应必会概念「生成器适合惰性处理大数据」） |
| 日志/计时/重试/缓存/鉴权等正交逻辑 | 装饰器 | 横切注入，业务函数保持纯净（呼应必会概念「装饰器适合横切逻辑」） |
| 需要保证释放的资源（文件/锁/连接/事务） | `with` + 上下文管理器/`contextlib` | 异常安全、防遗忘；事务 commit/rollback 语义（呼应 roadmap 必会概念） |
| 子类自动注册/插件表 | `__init_subclass__` | 两行代码，胜过元类（呼应必会概念「元类和描述符要谨慎使用」） |
| 进程内纯数据容器 | `@dataclass` | 零依赖、代码生成、可读性好（3.8） |
| 信任边界上的数据校验 | pydantic | fail-fast + 类型转换 + JSON（3.8；用法深讲在 ph10） |
| 高并发 IO 服务 | asyncio/uvicorn（用法在 ph14/ph16） | 机制理解在 3.9/4.4——选型时需要知道「一个进程为什么够」 |
| 性能热点（纯 Python 循环） | 先换算法 → Cython 加类型 → C 扩展 | 四代形态成本递增，3.10 的对比表 |

**不适合此阶段/这些机制的事项**：不需要的「高级」——**普通业务代码用装饰器/描述符/元类叠床架屋，是反模式**（判据：去掉它行为不变量依然成立、可读性提升，就别用）；CPython 的引用计数与 GIL 是**实现细节而非语言规范**（PyPy/Jython 无 GIL 也成立）——本阶段的机制结论只承诺 CPython 3.13 标准构建；「Python 太慢」的最终解是换语言/换运行时（Go/Rust/C 各语言路线），C 扩展只是 Python 侧的补丁。

**与其他语言同类机制的对比**（一句话级，为 analysis/ 与 Tenet 合成积累素材）：**装饰器 ≈ 注解/AOP 的一部分**——Java 注解是声明不执行、靠框架反射读取，Python 装饰器是定义期直接执行的可调用对象（更灵活也更隐式）；**生成器 ≈ Rust/Go 迭代器模式、JS 生成器**——Python 用暂停帧实现，Rust 用状态机结构体实现（无运行时暂停成本）；**上下文管理器 ≈ C++ RAII 的语法化**——C++ 靠析构函数在作用域出口隐式执行，Python 把「出口动作」显式成 `with` 块与 `__exit__`（更可见、可吞异常）；**GIL ≈ 无**——Go/Rust 用线程安全类型系统/无共享心智绕开了「解释器全局锁」这个设计，是 CPython 为引用计数简单性付的历史税。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条验证。验证环境：Python 3.13.9 + pytest 8 + ruff 0.12（目标工具链）；pydantic 2.x 仅 ex06 需要。**全部示例已验证**（Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 本机实测：main 自检、pytest 断言、ruff check/format 全绿），运行命令见文件头与 README。

### 示例 1：迭代器协议与生成器进阶（呼应 3.1/3.2）

完整文件 `examples/ex01-iterator-generator.py`：手写迭代器、`for` 循环展开、`iter()` 的回退协议（`__getitem__` 序列兜底）、生成器惰性（对比内存）、`send`/`throw`/`close`、`yield from` 链与子生成器返回值。

```python
# examples/ex01-iterator-generator.py —— 迭代器/生成器协议演示
def gen_echo() -> Iterator[str]:   # send 双向通信：yield 表达式的值 = send 的参数
    got = yield "ready"            # 首次 send(None)/next 走到这，产出 ready
    yield f"got:{got}"

c = gen_countdown(3)
print("next 推进:", next(c), "-> 剩余:", list(c))   # next: 3 -> 剩余: [2, 1]
e = gen_echo()
print("send 启动:", next(e), "| send 注入:", e.send("ping"))
# 输出：send 启动: ready | send 注入: got:ping
```

运行：`python3 ex01-iterator-generator.py`（main 自检断言，全部通过静默退出）；测试：`python3 -m pytest ex01-iterator-generator.py -q`。

### 示例 2：装饰器进阶（呼应 3.3）

完整文件 `examples/ex02-decorators-advanced.py`：闭包演示（计数器/延迟求值）、`wraps` 的重要性（对比有无 `@wraps` 的 `__name__`）、带参装饰器（重试）、装饰器叠加顺序、类装饰器（调用计数）、`functools.lru_cache` 与 `singledispatch`。

### 示例 3：上下文管理器与 contextlib（呼应 3.4）

完整文件 `examples/ex03-context-managers.py`：手写类上下文管理器（计时/文件）、异常语义（吞/传/替换）、`@contextmanager` 等价实现、`ExitStack` 动态管理、`suppress`、`closing`、事务形态（异常时 rollback 语义）。

### 示例 4：描述符与元类（呼应 3.5/3.6）

完整文件 `examples/ex04-descriptor-metaclass.py`：手写 `my_property`/`my_classmethod` 等价描述符、data vs 非 data 描述符优先级实测、`__set_name__` 自动收名、`__init_subclass__` 注册表 vs 元类注册表对照、元类改写类体。

### 示例 5：协程与事件循环原理（呼应 3.9/4.4）

完整文件 `examples/ex05-coroutine-eventloop.py`：协程对象惰性（调用不执行体）、手写极简任务调度器（就绪队列驱动 `async def` + `types.coroutine` 模拟 awaitable）与 asyncio 对照、`Task`/回调观察、`asyncio.sleep(0)` 让出次序演示、模拟「千个挂起任务由一个循环驱动」的规模论证。

### 示例 6：dataclass 机制与数据类三选一（呼应 3.8）

完整文件 `examples/ex06-dataclass-pydantic.py`：`@dataclass` 生成的 `__init__`/`__repr__`/`__eq__` 观察、`field(default_factory)` 防共享、`frozen`/`asdict`/`replace`、`__post_init__` 派生字段，dataclass vs pydantic（类型校验/转换/失败行为）同数据对比，`TypeAdapter` 桥接 dataclass。依赖 pydantic 2.x（`python3 -m pip install "pydantic>=2"`）。

### 示例 7：import 机制与内存管理（呼应 3.7/4.1/4.2/3.10）

完整文件 `examples/ex07-import-gc-memory.py`：`sys.path`/`sys.modules` 侦察、`importlib` 动态导入与重载、循环导入陷阱复现（最小双模块）、引用计数观察（`sys.getrefcount`）、循环引用 + `gc.collect()` 回收验证、`weakref` 失效回调、`__slots__` 无 `__dict__` 断言、小整数驻留实测、ctypes 调 libc 最小形态。

## 7. 总结

### 关键要点

1. **协议优先于类层级**（必会概念的心智底座）：迭代器（`__iter__`/`__next__`/`StopIteration`）、上下文管理器（`__enter__`/`__exit__`）、描述符（`__get__`/`__set__`/`__delete__`）都是「实现协议即被机制接纳」——`for` 不认识列表，只认识可迭代对象（3.1/3.4/3.5）
2. **生成器 = 暂停的帧**：`yield` 保存执行状态按需产出，内存 O(1)（3.2）；`send`/`throw`/`yield from` 让生成器可组合、可双向通信（PEP 342/380 的历史沉淀）
3. **装饰器 = 定义期横切钩子**：闭包 + 一等函数；`functools.wraps` 保函数身份；带参装饰器三层嵌套；叠加自下而上（3.3）
4. **描述符解释整个对象模型**：方法绑定、`property`/`classmethod`/`staticmethod` 都是描述符的现成实现；data 描述符先于实例字典（3.5）
5. **元类要克制**：`__init_subclass__`/`__set_name__`/类装饰器覆盖 90% 场景，自定义元类只留给「改变类创建流程」本身（3.6）
6. **import 是运行时行为**：`sys.path` 找、`sys.modules` 缓存、模块体只执行一次；循环导入 = 半成品模块；相对导入只在包内有效（3.7）
7. **数据类三选一**：内部容器 dataclass（stdlib）、边界校验 pydantic（fail-fast + Rust 核心）、中间带 attrs——先判数据从哪来，再选容器（3.8）
8. **协程原理 = 帧暂停 + 事件循环调度**：await 挂起、Task 步进、IO 就绪回调唤醒——这就是 uvicorn 单进程上千连接的答案（3.9/4.4）
9. **GIL 是引用计数简单性的历史税**：计算占锁（5ms 时间片）、等待放锁（IO 重叠）；CPU 密集靠多进程（ph14 实测、ph16 pre-fork），free-threaded 是 3.13 起的渐进出路（4.3）
10. **内存 = 引用计数（及时） + 分代 GC（补循环引用）**：`__del__` 不可依赖、缓存用 weakref、百万实例用 `__slots__`（4.1/4.2）
11. **性能边界四代形态**：ctypes 调、cffi 绑、C API 写、Cython 渐进——只对热点，且按成本递增（3.10）
12. **验证纪律**：全部代码已在 Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 本机实测通过（main 自检与 pytest 断言全绿、ruff check/format 全绿），文件头与 README 标注「已验证」——请按文件头命令复现即可

### 阶段验收清单

- [ ] 能手写迭代器并解释 `for` 循环展开；能说清「可迭代 ≠ 迭代器」（对应 roadmap「能写生成器和装饰器」）
- [ ] 能写带 `send`/`yield from` 的生成器处理大文件（流式、内存 O(1)）；能解释生成器为什么惰性
- [ ] 能写 `functools.wraps` 的计时/重试装饰器与类装饰器；能解释装饰器叠加顺序与定义期执行
- [ ] 能手写与 `property` 等价的描述符；能说清 data 描述符与实例字典的优先级
- [ ] 能用 `__init_subclass__` 做注册表，并说明「何时才需要元类」（呼应必会概念「元类和描述符要谨慎使用」）
- [ ] 能解释 `sys.path`/`sys.modules`/循环导入/相对导入陷阱（对应 roadmap「能判断高级特性是否必要」的心智部分）
- [ ] 能说清 dataclass/attrs/pydantic 的取舍判据，并解释 dataclass 的代码生成机制
- [ ] 能解释「await 挂起时事件循环内部发生了什么」与「uvicorn 单进程为什么能服务上千连接」（对应 roadmap「能解释 GIL 影响」之外的协程原理）
- [ ] 能解释 GIL 为什么存在、何时切换、对 CPU/IO 密集的影响，并简述 3.13 free-threaded 是什么
- [ ] 能解释引用计数 + 分代 GC 如何互补、循环引用怎么被回收、为什么 `__del__` 不可依赖
- [ ] 能跑通 examples/ 全部示例（`python3 ex0X-*.py` 与 `python3 -m pytest ex0X-*.py -q`）并解释输出

### 跨语言对比：高级特性与运行时

| 维度 | Python | Rust | Go | Java |
|------|--------|------|----|------|
| 横切逻辑 | 装饰器（定义期执行的可调用对象） | 属性宏/函数宏（编译期展开） | 无一等语法（靠包装函数/接口） | 注解（声明，靠框架反射） |
| 惰性序列 | 生成器（暂停帧） | 迭代器（`Iterator` trait + 惰性适配器） | 无内建生成器（goroutine/channel 近义） | Stream（对象组合） |
| 资源管理 | `with` + 协议（显式块） | RAII（析构即作用域出口） | `defer`（函数级延迟） | try-with-resources |
| 对象访问拦截 | 描述符/`__getattr__` | trait 方法（无隐式拦截） | 接口方法 | 动态代理/字节码 |
| 并发原语 | GIL 阴影下的线程/进程/async | 所有权 + async（无 GC 锁） | goroutine（语言级调度） | 线程池/JVM |
| 元编程 | 元类/装饰器/`__init_subclass__` | 宏/derive | `go:generate`/反射 | 注解处理器/反射 |

一句话：**Python 的高级特性把「运行时反射 + 协议」推到极致——灵活但隐式；Rust/Go 把同样的横切与惰性在编译期/类型层解决，代价是写起来更重**（为 analysis/ 与 Tenet 合成积累素材：元编程强度与运行时开销正相关）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。对应 roadmap 第 17 节「练习」小节四个题目：计时装饰器（练习 1）、重试装饰器（练习 2）、上下文管理器（练习 3）、生成器处理大文件（练习 4），另加 1 道描述符/元类进阶题（练习 5），完成 5 题后继续：

- 计时装饰器（★）：`@wraps` + 累计耗时统计
- 重试装饰器（★★）：带参重试 + 退避 + 异常白名单
- 上下文管理器（★★）：事务语义（异常 rollback）+ `@contextmanager` 写法对照
- 生成器处理大文件（★★）：流式解析 + 惰性统计（内存与文件无关）
- 描述符与注册表（★★★）：只读/校验描述符 + `__init_subclass__` 注册表

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**流式日志处理器（streamlog）**——用生成器做流式读取与解析管线（内存与文件大小无关）、装饰器做管线阶段的横切统计（计时/计数）、上下文管理器做文件与输出缓冲的资源管理、dataclass 做结构化记录——四层协议（迭代/装饰/资源/数据容器）在一个真实工具里合流，对应 roadmap「推荐项目」第一个「流式日志处理器」（第二个「可复用装饰器库」由练习 1/2 与 examples/ex02 覆盖）。建议完成练习后再动手，练习 4（生成器大文件）是它的核心缩小版。

- [ ] 完成 exercises/ 全部 5 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`python3 -m pytest` 全绿；`ruff check .` 与 `ruff format --check .` 通过；`python3 -m streamlog.cli --file demo.log --stats` 输出正确统计）

### 下一阶段

[**ph18 车联网 / 数据平台 / 自动化方向阶段**](../ph18-iot-data-automation/18-iot-data-automation.md)（roadmap 第 18 节——Python 路线的最后一个阶段，现已建成）——把本阶段攒下的机制理解放进真实行业场景：CAN 日志解析（本阶段 project/ 的流式解析管线直接升级为 CAN 总线日志的按 ID 流式统计）、车辆遥测数据处理与电池数据分析（ph09/ph15 的技能 + 本阶段的惰性与性能认知，处理海量时序数据时知道瓶颈在哪）、自动化测试平台（ph13 方法论 + 本阶段的装饰器/上下文管理器写可复用的测试基础设施）、FastAPI 数据服务（ph10/ph16 的服务栈 + 事件循环原理）与 AI 异常检测。本阶段的「生成器流式 + 协议化资源管理」会在 CAN 日志这类「几十 MB 起步、逐行解析」的任务里立刻兑现价值。
