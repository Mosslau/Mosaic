# exercises —— 高级 Python 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap 第 17 节「练习」小节一一对应：计时装饰器（练习 1）、重试装饰器（练习 2）、上下文管理器（练习 3）、生成器处理大文件（练习 4），另加 1 道描述符/元类进阶题（练习 5，呼应 roadmap 必会概念「元类和描述符要谨慎使用」——通过把它写对来理解它）。完成顺序建议按 1~5：先用装饰器（横切）、再上下文管理器（资源）、再生成器（大文件）、最后挑战协议层。

## 依赖与验证方式

- 依赖：无第三方依赖（纯标准库）；验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12
- 运行：`python3 sol-0X-*.py`（每个参考实现带 main 自检，断言失败会报错退出）；测试：`python3 -m pytest sol-0X-*.py -q`
- lint：`ruff check sol-0X-*.py` 或本目录 `ruff check .`（配置见 [`pyproject.toml`](./pyproject.toml)）
- 参考实现文件头带**验证块**（环境、验证命令、验证状态）；**全部已验证**（Python 3.13.9 + pytest 8.4.2 本机实测：各 sol 运行自检与 pytest 断言均通过）

## 练习 1：计时装饰器（★）

- **目标**：写一个可复用的计时装饰器，累计每个被装饰函数的调用次数与总耗时（对应 roadmap「计时装饰器」）
- **要求**：
  - 用 `functools.wraps` 保持函数身份（`help()`、`__name__` 不被污染）
  - 记录并暴露 `calls`（调用次数）与 `total_time`（累计秒数），能按需重置
  - 装饰器本身要支持 `@timed` 与 `@timed(unit="ms")` 两种写法（带参与不带参都行——提示：默认参数法或判断首参是否可调用）
  - 被装饰函数抛异常时也要计入耗时与次数（`finally`）
- **验收**：`f.add(1, 2)` 连续调用后 `f.calls == 3`、`f.total_time > 0`；`f.__name__ == "add"`；`python3 -m pytest sol-01-timer-decorator.py -q` 全绿（把实际输出写进验证块）

## 练习 2：重试装饰器（★★）

- **目标**：写一个带参重试装饰器，让「可能瞬态失败」的函数自动重试（对应 roadmap「重试装饰器」）
- **要求**：
  - 接口 `@retry(times=3, delay=0.1, exceptions=(ConnectionError, TimeoutError))`：白名单异常才重试，白名单外直接抛
  - 每次重试之间 `time.sleep(delay)`；重试耗尽后抛出**最后一次异常**（`raise` 不带参数重抛或记录最后一次后抛）
  - 用 `functools.wraps`；用 `monkeypatch`/注入可重试函数的方式在测试里避免真 sleep（提示：delay 参数可传 0）
  - 加分项：记录每次失败原因（`last_error` 属性）
- **验收**：前 N-1 次抛 `ConnectionError`、最后一次成功的函数返回正确值且 `retry` 不多打一次；白名单外异常**立即**抛出不重试；`python3 -m pytest sol-02-retry-decorator.py -q` 全绿

## 练习 3：上下文管理器（★★）

- **目标**：写一个带事务语义的上下文管理器（对应 roadmap「上下文管理器」），并给出 `@contextmanager` 写法对照
- **要求**：
  - 类形态 `Transaction(conn)`：`__enter__` 开事务，`__exit__` 按 `exc_type is None` 决定 commit / rollback；`conn` 用最简单的假连接（记录操作列表）即可
  - `@contextmanager` 形态 `transaction_cm(conn)`：功能与类形态等价，块内异常**吞掉时返回 True、不吞时重新抛出**的语义要对齐（提示：try/except 包住 yield）
  - 验证：正常块 → commit 被调用、rollback 未调用；块内抛异常 → rollback 被调用、异常仍传播到外层
  - 加分项：`contextlib.ExitStack` 同时管理「日志文件 + 事务」两个资源
- **验收**：假连接的操作记录断言三种路径（正常 commit / 异常 rollback / 异常仍可见）；`python3 -m pytest sol-03-context-manager.py -q` 全绿

## 练习 4：生成器处理大文件（★★）

- **目标**：用生成器流式解析一个大日志文件，内存占用与文件大小无关（对应 roadmap「生成器处理大文件」）
- **要求**：
  - 要求输入文件不存在也能优雅处理（提示：文件不存在时报错信息要友好，或让调用方决定——选一种并说明）
  - 写一个 `parse_lines(path)` 生成器：逐行产出结构化记录（`(level, message)` 元组或小 dataclass），行解析用字符串方法或正则均可
  - 写 `count_levels(records)`：**消费生成器**并统计各 level 数量——不得把整个文件读进内存（`for line in file` 就是流式的，`file.readlines()` 不是）
  - 测试数据：用 `tempfile` 现场生成一个 10 万行的临时文件（可只做 1 万行，够验证流式即可），断言统计结果正确
  - 加分项：`itertools.islice` 只取前 N 条、或对记录再做一层 `filter` 生成器（演示生成器链）
- **验收**：统计结果与逐行手算一致；用一个「读取时打印文件偏移/不落盘」的探针或直接断言「解析函数不调用 `readlines()`/`read()`」来证明流式；`python3 -m pytest sol-04-generator-large-file.py -q` 全绿

## 练习 5：描述符与 `__init_subclass__` 注册表（★★★）

- **目标**：写一个校验型描述符与一个自动注册机制，理解「什么时候值得用协议层」（呼应必会概念「元类和描述符要谨慎使用」）
- **要求**：
  - 描述符 `Positive`：绑定到类的整数属性，赋值 < 0 时抛 `ValueError`；用 `__set_name__` 记录属性名（不得在类里写死字段名）
  - 用 data descriptor 的优先级说明「为什么赋值被它接管而不是写进实例 `__dict__`」
  - 注册表：`BaseCommand` 定义 `__init_subclass__`，任何子类定义即注册进 `BaseCommand.commands`（按类名索引）；写一个 `run(name, *args)` 分派函数按名字查表调用
  - 不加分项也行——但**禁止用自定义元类**完成本题（这正是本题的教学点：`__init_subclass__` 覆盖了元类 90% 的场景）
- **验收**：`Positive` 字段赋值负数抛 `ValueError`、正数正常；定义 `CmdA`/`CmdB` 后 `sorted(BaseCommand.commands)` 恰好含二者；`run("CmdA", ...)` 正确分派；`python3 -m pytest sol-05-descriptor-metaclass.py -q` 全绿

> **提示**：练习 1~5 与主文档 3.x 小节一一对应（3.3 装饰器、3.4 上下文管理器、3.2 生成器、3.5/3.6 描述符与注册表）；examples/ 的 ex01~ex05 是它们的「已给最小形态」，卡住时先跑 examples 再做题。做完后对照 sol-* 参考实现复盘——先独立完成，再看答案。
