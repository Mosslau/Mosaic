# examples —— 高级 Python 阶段完整示例

> 每个示例对应主文档 `17-advanced-python.md` 相关小节（3.1~3.10 / 第 4 章）的完整可运行版。验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12；仅 ex06 需要 pydantic 2.x（`python3 -m pip install "pydantic>=2"`）。**全部示例已验证**（Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 本机实测：运行自检通过、pytest 全绿、ruff check/format 全绿）。

| 文件 | 说明（对应主文档小节） | 运行 / 测试 |
|------|------|------------|
| `ex01-iterator-generator.py` | 迭代器协议、`for` 展开、`iter()` 回退、生成器惰性、`send`/`throw`/`close`、`yield from`（3.1/3.2） | `python3 ex01-iterator-generator.py`；`python3 -m pytest ex01-iterator-generator.py -q` |
| `ex02-decorators-advanced.py` | 闭包、`wraps`、带参装饰器、叠加顺序、类装饰器、`lru_cache`/`singledispatch`（3.3） | `python3 ex02-decorators-advanced.py`；`python3 -m pytest ex02-decorators-advanced.py -q` |
| `ex03-context-managers.py` | 上下文管理器协议（异常三态）、`@contextmanager`、`ExitStack`、`suppress`、事务形态（3.4） | `python3 ex03-context-managers.py`；`python3 -m pytest ex03-context-managers.py -q` |
| `ex04-descriptor-metaclass.py` | 手写 property/classmethod 等价描述符、data vs 非 data 优先级、`__set_name__`、`__init_subclass__` 注册表 vs 元类（3.5/3.6） | `python3 ex04-descriptor-metaclass.py`；`python3 -m pytest ex04-descriptor-metaclass.py -q` |
| `ex05-coroutine-eventloop.py` | 协程对象惰性、手写极简调度器 vs asyncio、Task/回调、`sleep(0)` 让出次序、千级挂起任务论证（3.9/4.4） | `python3 ex05-coroutine-eventloop.py`；`python3 -m pytest ex05-coroutine-eventloop.py -q` |
| `ex06-dataclass-pydantic.py` | dataclass 代码生成机制、`field`/`frozen`/`__post_init__`、与 pydantic 校验行为对比、`TypeAdapter` 桥接（3.8） | `python3 ex06-dataclass-pydantic.py`；`python3 -m pytest ex06-dataclass-pydantic.py -q`（需 pydantic 2.x） |
| `ex07-import-gc-memory.py` | `sys.path`/`sys.modules`/`importlib`、引用计数、循环引用 + gc、weakref、`__slots__`、小整数驻留、ctypes 调 libc（3.7/4.1/4.2/3.10） | `python3 ex07-import-gc-memory.py`；`python3 -m pytest ex07-import-gc-memory.py -q` |

说明：

- **每个示例都是「main 自检 + pytest 断言」双形态**：`python3 ex0X-*.py` 打印教学输出并跑断言（失败退出码非 0）；`python3 -m pytest ex0X-*.py -q` 只收集文件内 `test_*` 函数跑断言（pytest 8 默认 importlib 导入模式支持连字符文件名）。两者均在本机实测通过（已验证）
- **产物纪律**：示例不写临时文件、不起后台进程、不做网络请求，运行后工作区干净
- **lint**：本目录 `ruff check .` 与 `ruff format --check .`（配置见 [`pyproject.toml`](./pyproject.toml)）；本机实测全绿（已验证）
- ex05 依赖 `types.coroutine` 与标准库 asyncio 做「手写 vs 官方」对照，无第三方依赖；ex07 的 ctypes 片段调用 libc 的 `strlen`（macOS/Linux 均可用，`CDLL(None)` 取当前进程已加载库）
- ex06 若未安装 pydantic 2.x：`python3 -m pip install "pydantic>=2"`；pyproject 的 ruff 配置不含依赖声明，pydantic 只为运行 ex06 需要
