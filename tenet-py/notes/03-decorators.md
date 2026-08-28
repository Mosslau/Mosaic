# 03 · 装饰器与闭包（函数是一等公民）

> demo: `python3 demos/03_decorators.py`

## 1. 设计动机

很多语言里函数是"二等公民"：不能当参数传、不能当返回值。Python 的命题：
**函数就是普通对象**——可以存在变量里、传进函数、从函数返回。
这个看似简单的决定催生了闭包、高阶函数、装饰器（语法糖）等一整套能力。

## 2. 机制拆解

**闭包**：内层函数捕获外层函数的变量，外层结束后依然能用：

```python
def make_counter():
    count = 0
    def inc():            # 闭包：捕获 count
        nonlocal count
        count += 1
        return count
    return inc

c = make_counter()
c()  # 1
c()  # 2   ← count 活在内层函数的"环境"里
```

**装饰器**：`@deco` 只是 `f = deco(f)` 的语法糖——在函数定义时包装它：

```python
def timing(fn):
    def wrapper(*args):
        start = time.time()
        result = fn(*args)
        print(f"{fn.__name__} 耗时 {time.time()-start:.6f}s")
        return result
    return wrapper

@timing        # 等价于 fib = timing(fib)
def fib(n): ...
```

## 3. 代码验证（demos/03_decorators.py）

demo 演示：闭包计数器、`@timing` 装饰器、带参数的装饰器。

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 心智负担 | 闭包/作用域规则（nonlocal、late binding）是常见坑 |
| 调试困难 | 装饰器层层包装后堆栈难读 |
| 滥用风险 | 装饰器可以"隐式改行为"，项目里难维护 |

**换来的**：极高的表达力——AOP 风格的横切逻辑（日志/计时/权限）无需侵入业务代码。

## 5. 对 Tenet 的启示

- ✅ **吸收"横切逻辑与业务解耦"的思维**：Tenet 解释器的错误处理贯穿全链路、
  `print` 统一格式化——这些"横切关注点"集中实现，正是装饰器想解决的问题
- ✅ **吸收"函数是基本抽象单元"**：Tenet 的 `fn` 就是头等抽象——
  但**不是**一等值（不能把函数当参数/返回值），这是刻意的最小化
- ❌ **拒绝闭包/函数值**：Tenet 的函数表是全局的、函数只能按名调用——
  避免引入函数类型、捕获环境等复杂度（见 `lang/tenet` 演进方向）
- 💡 若未来加闭包，可参照 Python 的"闭包 = 函数 + 捕获的环境"，
  这也正是解释器里 Env 引用的自然延伸

**一句话**：Python 用「函数是一等公民」解锁闭包与装饰器；Tenet 保留
「函数是核心抽象」但砍掉函数值，用最少的机制拿到大部分收益。
