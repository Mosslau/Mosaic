# Python 测试与工程质量阶段

> 面向「怎么证明代码是对的、怎么防止改坏」，本阶段从 pytest 起步，把测试体系（fixture / mock / 参数化 / 覆盖率）与静态质量门禁（mypy 类型检查、ruff / black 格式与 lint、pre-commit 钩子、CI 流水线）串成一条可执行的工程质量流水线——这是 Python 从「能跑的脚本」走向「可维护的工程代码」的分水岭。

## 1. 概述

Python 测试与工程质量阶段的目标是：**写出可靠、可维护的 Python 工程代码**（roadmap 第 13 节目标）。它是整个学习路线的「工程质量」一站，承接两条线索：ph08 第三方库阶段已把 pytest/ruff 作为生态工具点到（「用 pytest/ruff 保障质量」，并在其第 6 章预告「下一步接入 pre-commit/CI（ph13）」）；ph12 自动化脚本阶段随手写的自检断言与错误处理（`pytest.raises` 之外的手工 `assert`、无效行计数、幂等重跑），在这里升级为系统的测试体系——**「证明代码是对的」从自觉变成制度**。本阶段把五个必会概念逐一落地：pytest 是工程测试主力、类型注解提升可维护性、格式化和 lint 应自动化、mock 用于隔离外部依赖，外加覆盖率作为「测了多少」的度量。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 测试框架 | pytest 断言与异常测试、`tmp_path` 临时文件、fixture 作用域与依赖注入、参数化测试 |
| 隔离外部依赖 | `unittest.mock` 的 `patch` / `MagicMock` / `side_effect`，让测试离线、快、可复现 |
| 覆盖率 | 标准库 `trace` 模块实测语句覆盖率，理解「覆盖率 100% 不等于没有 bug」 |
| 类型质量 | 类型注解、`@dataclass`、联合类型、Protocol，mypy 静态检查 |
| 代码风格 | ruff lint + 格式、black 格式、`pyproject.toml` 统一配置 |
| 门禁自动化 | pre-commit 本地钩子、GitHub Actions CI 流水线（pytest / ruff / mypy / black / 覆盖率） |

这个阶段只涉及**测试与工程质量工具链本身**（pytest / fixture / mock / 参数化 / 覆盖率、mypy、ruff / black、pre-commit、CI 门禁配置），**不涉及并发与异步代码的测试（pytest-asyncio、多线程/多进程下的测试策略）、生产环境部署与平台级 DevOps（Docker 化、监控告警、流水线平台运维）和数据分析结果的正确性验证（pandas 透视表与可视化校验）** — 那些是 ph14 并发、并行与异步阶段（roadmap 第 14 节，目录待建）、ph16 部署与 DevOps 阶段（roadmap 第 16 节，目录待建）和 ph09 数据分析阶段的内容。本阶段承接 ph12 自动化脚本阶段——脚本能跑只是起点，怎么证明它永远对、改不坏，是工程化必须回答的问题。**ph13 是当前学习路线的最后一个已建目录阶段**（ph14 起目录待建），本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

「测试与工程质量」是 Python 工程生态在过去二十多年里逐步制度化的结果。**单元测试传统**来自 xUnit 家族——Kent Beck 1994 年的 SUnit 确立「测试方法、断言、setup/teardown」的基本形态，1997 年 JUnit 把它固化为主流开发流程的一环。**Python 侧三条线并行演进**：测试框架线——Steve Purcell 的 PyUnit 于 2001 年并入标准库成为 `unittest`；2004 年 Holger Krekel 发起 **py.test**（最初是为 PyPy 写测试而生），以「原生 `assert` + fixture + 参数化」大幅降低写测试的门槛，2010 年代成为事实标准，2016 年发布 3.0 后正式以 **pytest** 命名；2008 年 Michael Foord 创建 **mock** 库解决「被测代码依赖外部世界」的问题，2012 年随 Python 3.3 进入标准库 `unittest.mock`。类型检查线——2012 年 Jukka Lehtosalo 创建 **mypy**，2014 年 PEP 484 定义了类型注解语法、Python 3.5 引入 `typing` 模块，mypy 从此成为「渐进式类型检查」的旗手。代码风格线——2018 年 Łukasz Langa 发布 **black**（「不容妥协的格式化器」，把 PEP 8 从建议变成机器的唯一输出），2017 年前后 Anthony Sottile 的 **pre-commit** 把质量门禁挂上 Git 钩子，2022 年 Astral 用 Rust 重写 lint/format 为一体发布 **ruff**（速度比 flake8 快数十倍，宣告「flake8/black/isort 各管一段」的工具链碎片化时代结束）；2019 年 GitHub Actions 让 CI 流水线进入每个仓库的云端。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| PyUnit / unittest 进标准库 | 2001 | Python 官方单元测试框架（Steve Purcell 的 PyUnit 合并入 CPython） |
| pytest 前身 py.test 诞生 | 2004 | Holger Krekel 发起，最初为 PyPy 写测试而生 |
| mock 库 | 2008 | Michael Foord 创建，测试替身的事实标准 |
| unittest.mock 进标准库 | 2012（3.3） | mock 成为官方标准库模块 |
| mypy / PEP 484 | 2012-2015 | Jukka Lehtosalo 创建 mypy；PEP 484 定义注解语法，Python 3.5 引入 typing |
| black | 2018 | Łukasz Langa 发布「不容妥协」的格式化器，PEP 8 的机器执行 |
| pre-commit | 2017 起 | Anthony Sottile 的 Git 钩子框架，把门禁挡在 commit 之前 |
| GitHub Actions | 2019 | CI/CD 平台普及，质量门禁进入云端流水线 |
| pytest 3.0 / 正式命名 | 2016 | py.test 更名 pytest，fixture 体系成熟 |
| ruff | 2022 | Astral 用 Rust 重写 lint + format，工具链一体化 |

本文示例以 **Python 3.13.9** 为基线（本机验证工具链实测版本），验证工具链 pytest 8.4.2 + ruff 0.12.0 + mypy 1.17.1 + black 25.9.0（全部已装并实测）；**pytest-cov 与 pre-commit 本环境未安装**——覆盖率改用标准库 `trace` 模块实测（命令见 [`examples/README.md`](./examples/README.md)），pre-commit 只提供配置示例（`project/.pre-commit-config.yaml`，未在本环境验证）。这个阶段的语法与 API 是 Python 工程生态中最稳定的部分——`unittest.mock` 自 3.3 起十余年未变，pytest 5.x 时代写的测试在 8.x 上几乎原样可跑，在测试上的投入长期有效。

## 3. 语法与参数

### 3.1 pytest 基础：断言与异常测试

**pytest 的约定是「零配置收集」**：文件里 `test_` 开头的函数（或 `Test` 开头类里的方法）会被自动收集为测试用例，每个用例就是「一段带断言的函数」。断言用 Python 原生 `assert` 语句——pytest 会重写它，失败时打印两侧的实际值（原理见 4.1）；「应当抛异常」用 `pytest.raises` 上下文管理器断言。`tmp_path` 是内置 fixture：每个用例一个独立临时目录，用完自动清理，测试互不污染。

```python
# examples/ex01-pytest-basics.py —— pytest 基础（完整版见示例 1，本机已验证）
def add(a: int, b: int) -> int:
    return a + b

def test_add_basic():
    assert add(1, 2) == 3          # 断言失败时 pytest 会打印两侧的实际值（见 4.1 断言重写）

def test_divide_by_zero_raises():
    # pytest.raises 断言「应当抛出指定异常」，抛不出来算失败
    with pytest.raises(ValueError):
        divide(1, 0)

def test_parse_score_write_read(tmp_path):
    # tmp_path：pytest 内置 fixture，每个用例一个独立临时目录，用完自动清理（主文档 3.2）
    f = tmp_path / "scores.txt"
    f.write_text("Alice,88\nBob,72\n", encoding="utf-8")
    lines = f.read_text(encoding="utf-8").splitlines()
    assert parse_score(lines[0]) == ("Alice", 88)
```

**pytest 常用断言姿势**

| 断言场景 | 写法 |
|---------|------|
| 相等/不相等 | `assert x == y` / `assert x != y` |
| 真值/假值 | `assert x` / `assert not x` |
| 成员/集合 | `assert "a" in s`、`assert set_a == {"x"}` |
| 应当抛异常 | `with pytest.raises(ValueError): ...` |
| 异常对象细节 | `with pytest.raises(ValueError) as ei: ...` 后查 `ei.value` |

**关键概念：用例 = 函数 + 断言**。pytest 不要求写类、不要求 `assertEqual` 这类专用方法——一个 `test_` 函数加一条 `assert` 就是最小用例，这正是它比 `unittest` 更「低摩擦」的原因。失败定位靠参数化与 `tmp_path` 的隔离性：每个用例独立，一个挂了不影响其他。

### 3.2 fixture：测试前置与共享状态

**fixture 是 pytest 的依赖注入机制**：测试函数声明参数名，pytest 自动构造并传入。三个进阶能力是本阶段重点：**作用域（scope）**——`scope="session"` 的 fixture 整个 pytest 会话只建一次，跨用例共享（如启动计数、昂贵连接）；**autouse**——不加参数也自动对每个用例生效（如统一建目录、统一清缓存）；**工厂模式与 yield 清理**——fixture `yield` 一个「造对象」的函数让数据随用例不同，`yield` 之后的代码是清理阶段，本用例结束时执行。

```python
# examples/ex02-fixture-scope.py —— fixture 进阶（完整版见示例 2，本机已验证）
@pytest.fixture(scope="session")
def session_counter():
    counter = {"setup": 0}
    counter["setup"] += 1            # 若每个用例都重建，这里会加多次
    return counter

def test_session_shared_1(session_counter):
    assert session_counter["setup"] == 1    # 整个 pytest 会话只建一次

def test_session_shared_2(session_counter):
    assert session_counter["setup"] == 1    # 第二次取到的是同一个对象（仍是 1，不是 2）

@pytest.fixture(autouse=True)
def _ensure_workdir(tmp_path):
    """autouse fixture：本文件每个用例自动创建 work 目录，测试不用写这个参数。"""
    (tmp_path / "work").mkdir(exist_ok=True)
    yield
```

**fixture 作用域对照**

| scope | 生命周期 | 典型用途 |
|-------|---------|---------|
| `function`（默认） | 每个用例一次 | 临时数据、文件、对象 |
| `class` / `module` | 每个类/模块一次 | 类内共享的只读资源 |
| `session` | 整个 pytest 会话一次 | 启动计数、昂贵连接、全局配置 |
| `package` | 每包一次（pytest 8.2+） | 包级共享 |

> **fixture 依赖另一个 fixture**：在 fixture 的参数里声明另一个 fixture 名，pytest 按依赖图自动先构造再注入（ex02 的 `data_file → store` 链）；`conftest.py` 里的 fixture 对同目录及以下的所有测试可见（project 落地）。本阶段只用函数级与 session 级作用域，**fixture 与参数化的交叉进阶（如按参数组生成 fixture）超出本阶段**，用到时查 pytest 文档即可。

**前后置与清理**：`yield` 把 fixture 切成「setup（yield 前）/ teardown（yield 后）」两段——写文件、建对象在 setup，删资源、断言「被测代码真的用了这个 fixture」在 teardown（ex02 的工厂 fixture 在 teardown 里断言工厂被用上了）。这是「测试后世界恢复原样」的制度保证。

### 3.3 mock：隔离外部依赖

**mock 解决「被测代码依赖外部世界」**：网络 API、时钟、随机数、文件系统在测试里不可控（会变、会挂、会慢），用 `unittest.mock` 的 `patch` 在运行期**替换掉真实依赖**，让被测代码以为在打真实接口、其实打的是测试造好的假响应。核心三件套：`patch`（替换目标，上下文管理器与装饰器两种写法等价）、`MagicMock`（自动模仿任意属性/方法调用的假对象）、`side_effect`（让 mock 调用时抛异常或按列表依次返回）。

```python
# examples/ex03-mock.py —— mock 外部依赖（完整版见示例 3，本机已验证，不会真的发请求）
def fetch_speed(vehicle_id: str, base_url: str = "https://api.example.com") -> float:
    resp = requests.get(f"{base_url}/vehicles/{vehicle_id}/speed", timeout=2)
    resp.raise_for_status()                 # 4xx/5xx 抛 HTTPError
    return float(resp.json()["speed"])

def test_success_with_context_manager():
    with patch("requests.get", return_value=fake_response(payload={"speed": 42.5})) as mock_get:
        assert fetch_speed("EV-001") == 42.5
    # 顺带断言「被测代码确实按预期调用了接口」——参数与 timeout 都不能错
    mock_get.assert_called_once_with(
        "https://api.example.com/vehicles/EV-001/speed", timeout=2
    )
```

**mock 三件套速查**

| 工具 | 作用 | 本阶段用法 |
|------|------|-----------|
| `patch("module.attr")` | 运行期替换 `module.attr`，with 块/装饰器结束后还原 | 替换 `requests.get`（注意打「使用处的名字」而非定义处，见 4.3） |
| `MagicMock()` | 自动模仿任意属性与调用 | 造假响应对象：`resp.json.return_value = {...}` |
| `side_effect` | 调用时抛异常 / 按序列返回 | 模拟 404（`HTTPError`）、超时（`ConnectTimeout`）、连续两次返回不同值 |

**断言「被测代码怎么调用的」**：`assert_called_once_with(...)` 核对调用参数（URL、`timeout=2`）、`call_count` 核对调用次数——mock 不仅让测试离线，还把「接口契约」钉死在测试里，接口参数被改坏立刻暴露（ex03 用例 1、练习 3）。

> ⚠️ **MagicMock 的自动模仿是把双刃剑**：没配返回值时它静默编造值——`float(mock)` 返回 1.0、下标取值也照常返回 mock，测试「看起来通过了」实际测的是假值（假阳性）。mock 的配置必须显式写清楚（ex03 用例 6 专门演示这个陷阱），这正是「mock 用于隔离外部依赖、但不能让被测逻辑本身跑在假值上」的边界。

### 3.4 参数化测试与覆盖率

**参数化让「一组数据 = 一个独立用例」**：`@pytest.mark.parametrize("参数名", [数据列表])` 把同一段测试逻辑展开成多个用例，失败时精确定位到哪组数据——边界值（0/30/120 分界点两侧）、非法输入枚举、极端值都靠它铺满。**覆盖率**回答「测了多少」：统计被测代码里多少条语句被测试执行过，本阶段用标准库 `trace` 模块实测（`pytest-cov` 未安装，命令见下），不引入第三方依赖。

```python
# examples/ex04-parametrize.py —— 参数化 + 覆盖率（完整版见示例 4，本机已验证）
@pytest.mark.parametrize("speed,expected", [
    (-1, "invalid"),        # 负数
    (0, "low"),             # 下边界
    (29.9, "low"),          # low 档上限内
    (30, "normal"),         # normal 档下边界（>=30）
    (120, "normal"),        # normal 档上边界（<=120）
    (120.1, "high"),        # 越界一丁点就进 high
    (999, "high"),          # 极端值
])
def test_categorize_speed(speed, expected):
    assert categorize_speed(speed) == expected
```

**覆盖率实测命令**（多步命令，按序执行）：

```bash
# 1. 跑参数化测试
python3 -m pytest ex04-parametrize.py -q

# 2. 用标准库 trace 实测语句覆盖率（--ignore-dir 换成你的 site-packages/标准库路径）
python3 -m trace --count --summary --coverdir /tmp/ph13-cover \
       --ignore-dir /opt/homebrew/anaconda3/lib/python3.13 \
       --module pytest ex04-parametrize.py -q
```

```text
# 3. summary 末尾给出每个模块的 行数 / 覆盖率
lines   cov%   module
   25   100%   ex04-parametrize
```

**关键认知：覆盖率 100% 不等于没有 bug**。它只证明「被覆盖的行都跑过」，不证明「跑过的行为是对的」（断言写得弱，全绿也白搭），更覆盖不到「没写的分支、没测的交互」——覆盖率是「测了多少」的度量，不是「对不对」的证明。工程上追求的是**关键分支的参数化铺满 + 断言写到位**，而不是单纯刷满数字（练习 4 把这一点写进验收）。

### 3.5 类型注解与 mypy：把类型错误挡在运行之前

**类型注解是给工具和人看的契约**：ph01 已见过 `def f(x: int) -> str` 的基本形态（PEP 484，Python 3.5+），ph04 面向对象阶段有意不展开 `@dataclass`（其边界声明里写明），这里一并补齐工程用法——`@dataclass` 自动生成 `__init__`/`__repr__`/`__eq__` 的数据容器、`X | None` 联合类型显式声明「可能没有值」、`Protocol` 结构类型声明「只要长这样就能用」。**mypy 是静态类型检查器**：在运行之前扫描代码，发现「把 int 赋给声明为 str 的变量」「对 float 调 upper()」这类类型错误——类型注解本身不改变运行行为（运行时被忽略），它的价值全在检查与自文档。

```python
# examples/ex05-mypy.py —— 类型注解 + mypy（完整版见示例 5，本机已验证）
@dataclass
class VehicleTelemetry:
    """一行遥测数据：车辆、速度、电量。"""
    vehicle_id: str
    speed: float
    battery: float

class Formatter(Protocol):
    """结构类型（Protocol）：任何带 format(VehicleTelemetry) -> str 的对象都可被接受。"""
    def format(self, t: VehicleTelemetry) -> str: ...

def find_vehicle(rows: list[VehicleTelemetry], vehicle_id: str) -> VehicleTelemetry | None:
    """找指定车辆的第一条记录；找不到返回 None（联合类型显式声明）。"""
    for r in rows:
        if r.vehicle_id == vehicle_id:
            return r
    return None
```

**故意出错的对照（ex05b）**：以下 4 处类型错误正是 mypy 要抓的典型：

```python
# examples/ex05b-mypy-bugs.py —— 故意出错示例（类型错误版）：仅供 mypy 检查演示，请勿直接运行
def total_speed(vehicles: list[Vehicle]) -> int:
    total = 0
    for v in vehicles:
        total += v.speed            # 错误 2: incompatible types —— float 累加进 int 变量
    return total

def main() -> None:
    x: str = add(1, 2)              # 错误 1: assignment —— int 赋给声明为 str 的变量
    v = Vehicle("EV-002", 30.0)
    print(v.speed.upper())          # 错误 3: attr-defined —— float 没有 upper 方法
    print(total, add("1", 2))       # 错误 4: arg-type —— str 传给声明为 int 的参数
```

**mypy 常见错误码对照**

| 错误码 | 含义 | 修法 |
|--------|------|------|
| `assignment` | 赋值与声明的类型不符 | 改声明或改赋值 |
| `incompatible types` | 运算/累加两侧类型冲突 | 统一类型（如 float 累加进 float 变量） |
| `attr-defined` | 该类型没有这个属性/方法 | 用对类型，或先判 `None`/`isinstance` |
| `arg-type` | 实参与形参类型不符 | 改调用或放宽形参 |

> **类型注解的基础语法属于 ph01/ph04 的内容，这里不再展开**；本阶段聚焦「注解怎么为工程服务」——`mypy` 静态检查（ex05/ex05b）、`Protocol` 结构类型（ex05）、以及「注解让调用方与工具链都能发现类型错误」的心智（练习 5）。`Any` 是渐进式类型系统的逃逸口：临时跳过检查可以，但它是债，不是解药（4.5）。

### 3.6 ruff 与 black：格式与 lint 自动化

**ruff 是「lint + 格式」一体的静态工具**（Rust 实现，2022 年发布，速度比 flake8 快数十倍），一条命令替代 flake8/pyflakes/isort/black 各自为政的旧格局；**black 是「不容妥协」的格式化器**——同一段代码只有一种输出，团队里不再有格式争论。二者分工：**ruff check 查「代码有没有问题」（未使用导入、未定义名称、裸 except、风格规则），ruff format / black 管「长什么样」（缩进、引号、行长、换行）**。配置统一进 `pyproject.toml`，全项目一个标准。

```toml
# examples/pyproject.toml —— ruff 校验基准（本机已验证，被 ruff 命令自动读取）
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

```python
# examples/ex06-ruff.py —— ruff 配置 + 干净代码（完整版见示例 6，本机已验证）
def merge_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """按 id 合并重复行：后面的字段覆盖前面的（演示常见数据处理）。"""
    merged: dict[str, dict[str, str]] = {}
    for r in rows:
        merged[r["id"]] = {**merged.get(r["id"], {}), **r}
    return list(merged.values())
```

**ruff 常用规则码速查**（`select` 里挑的 E/F/I/UP/B 是最常用的四组）：

| 规则码 | 管什么 | 例子 |
|--------|--------|------|
| E | pycodestyle 错误 | `E501` 行超长、`E722` 裸 except |
| F | pyflakes 错误 | `F401` 未使用导入、`F821` 未定义名称、`F841` 未使用变量 |
| I | isort 导入排序 | `I001` import 顺序错（字母序） |
| UP | pyupgrade 现代写法 | 老式 `Optional[X]` → `X | None` 等 |
| B | bugbear 反模式 | 容易写错的 bug 模式 |

**故意出错的对照（ex06b）**：6 处 lint 违规分别对应上表——`import sys` 后 `import os`（I001 顺序错）、`import json` 从未使用（F401）、`unused = result * 2` 从未使用（F841）、`except:` 裸 except（E722）、`print(undefined_name)` 未定义名称（F821）、超长行（E501）。**lint 是「机器可读的代码评审」**：这些错误运行时不一定会炸（F401/F841 只是浪费），但 F821 直接就是 NameError，裸 except 连 `KeyboardInterrupt` 一起吞——lint 把它们挡在提交之前。

> **black 与 ruff format 是同一个问题的两种工具**：black 是独立格式化器（2018），ruff 的 `ruff format` 与其输出对齐（同款风格、更快的实现）。本阶段工程里用 black 也行、用 `ruff format` 也行，**选定一个并让 CI 检查 `--check` 模式**即可（project 的 CI 两个都查）。

### 3.7 pre-commit 与 CI/CD：把门禁变成制度

**pre-commit 把质量门禁挂到 Git 钩子上**：`git commit` 之前自动跑配置的钩子（ruff、mypy、格式检查），没过就拦住提交——门禁从「靠自觉」变成「制度」。它用 `repos` 列表声明要跑的钩子与版本，首次运行会按配置下载钩子环境。**CI/CD（持续集成/持续交付）把同一套门禁搬到云端**：GitHub Actions 在每次 push / PR 时自动跑流水线（装依赖 → lint → 格式检查 → 类型检查 → 测试 + 覆盖率），任何人在任何机器上提交，结果都一样——**本地门禁管「进仓库之前」，CI 管「进仓库之后」**。

```yaml
# project/.pre-commit-config.yaml —— pre-commit 钩子示例（本环境未安装 pre-commit，未在本环境验证）
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.17.1
    hooks:
      - id: mypy
        args: [telemetry_stats, cli.py]
```

```yaml
# project/.github/workflows/ci.yml —— GitHub Actions 持续集成（本环境无 CI 平台，未在本环境验证）
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Lint (ruff)
        run: ruff check .
      - name: Format check (ruff format + black)
        run: |
          ruff format --check .
          black --check .
      - name: Type check (mypy)
        run: mypy telemetry_stats cli.py
      - name: Test with coverage (pytest-cov)
        run: pytest --cov=telemetry_stats --cov-report=term-missing
```

> **本阶段 CI/CD 只到「把本地门禁搬上云端流水线」的配置层面（多版本矩阵、依赖安装、四道检查）**，**Docker 化部署、监控告警与流水线平台运维属于 ph16 部署与 DevOps 阶段（roadmap 第 16 节，目录待建）**；pre-commit 本环境未安装，`project/.pre-commit-config.yaml` 是可直接使用的配置示例——装好 `pip install pre-commit` 后 `pre-commit install && pre-commit run --all-files` 即可生效（本地等价验证：`ruff check . && ruff format --check . && mypy telemetry_stats cli.py`，project 全部实测通过）。

## 4. 底层原理

### 4.1 pytest 的断言重写与用例收集

`assert add(1, 2) == 3` 失败时，pytest 打印的不只是「AssertionError」，而是 `assert 3 == 5` 两侧的实际值——靠的是 **断言重写（assertion rewriting）**：pytest 在收集测试文件时用 `ast` 解析源码，把 `assert X == Y` 重写成「求值 X、求值 Y、比较、失败时带上两侧值」的字节码。这就是「原生 assert 也能报出细节」的底层机制。用例收集走 `conftest.py` 目录层级 + 文件名/函数名约定：`test_*.py` 文件里的 `test_*` 函数（及 `Test*` 类的方法）被递归发现，`conftest.py` 里的 fixture 按目录作用域可见——理解了「收集是 AST 层的工作」，就理解了为什么断言重写对 `-O` 优化开关免疫、为什么测试文件可以放在被测代码旁边（ex01 的「生产函数与测试函数同文件」就是利用收集规则的最简形态）。

### 4.2 fixture 的生命周期与依赖解析

fixture 是 pytest 的**依赖注入容器**：每个 fixture 是一个「惰性构造 + 按需缓存」的提供者。pytest 先对用例参数做**依赖图拓扑排序**——`store(data_file)` 声明依赖 `data_file`，pytest 先构造 `data_file` 再把它注入 `store` 的参数，全部构造完才调用测试函数；`scope` 决定缓存粒度（`function` 每用例一次、`session` 整个会话一次，见 3.2 表格），`autouse` 的 fixture 被隐式挂到每个用例。`yield` 把「构造」与「清理」连成一条链：用例结束时按**依赖的反序**执行 teardown（先清理最内层的），保证「用完即还原」不依赖书写顺序。fixture 是测试里最值得投入理解的概念——它把「造数据」这个最高频动作从每个用例里抽出来，一次声明、处处注入。

```text
store ──依赖──▶ data_file ──依赖──▶ tmp_path
  │                │                  │
  └── 用例结束：按依赖反序清理 ◀───────┘
```

### 4.3 mock 的运行时替换机制

`patch("requests.get")` 为什么能拦住被测代码里的 `requests.get(...)`？因为 Python 的属性访问是**运行期名字查找**：`requests.get` 每次调用都查 `requests` 模块的 `get` 属性。`patch` 利用这一点，在进入上下文时把 `requests.get` 替换成 mock、退出时还原——**替换发生在「使用处的模块属性」上**，所以 patch 的目标必须写被测代码实际使用的名字（`requests.get`），而不是 requests 内部定义 `get` 的位置（打错地方 mock 不生效，这是最常见的坑）。`MagicMock` 的本质是「**任何属性访问都返回一个新的子 mock**」：`__getattr__` 被实现成「没有就现场造一个」，于是 `resp.json()` 不用配置就能调——但这正是 3.3 警告的假阳性来源：不显式配置 `return_value`，mock 就静默编造值。`side_effect` 则是 mock 调用时的「分派器」：传异常则抛、传列表则依次弹出、传函数则调用它——错误路径与序列行为都靠它模拟。

### 4.4 覆盖率统计原理：逐行插桩

标准库 `trace`（以及 pytest-cov 底层的 coverage 库）统计语句覆盖率的原理是**运行期插桩**：`trace` 通过 `sys.settrace` 在每个函数调用和每行代码执行时收到回调，记录「哪一行被执行过」，结束时用 AST 算出每个模块的**可执行语句清单**（跳过注释、空行、纯声明），两者相除得百分比。这个机制的三个推论：① 覆盖率是**语句覆盖（statement coverage）**，只数「行被执行」，不数「分支是否都走过」——`if/else` 两分支各测一半也算 100%；② 没被执行到的行可能是「漏测的分支」也可能是「死代码」，要人工分辨；③ 插桩本身有开销与精度噪声（`trace` 对 pytest 自身模块也计数，所以 `--ignore-dir` 指向标准库路径，见 3.4 命令）。想更深可换 `pytest-cov`（branch 覆盖、HTML 报告），原理相同、体验更好——本阶段用 `trace` 是为了零安装。

### 4.5 mypy 的渐进式类型检查

mypy 是**静态类型检查器**：不运行代码，直接对源码做**类型推断**——从注解与字面量出发，沿数据流推导每个表达式的类型，与声明比对，不一致就报错（ex05b 的 4 处错误全是推断值与声明值的冲突）。三个关键设计：① **渐进式类型系统**：没写注解的地方默认是 `Any`，`Any` 与任何类型都兼容——所以「全项目零注解」时 mypy 等于什么都没查，注解覆盖率决定检查强度；② **注解不改变运行行为**：类型注解在运行时被忽略（`def f(x: int)` 传字符串照样运行），mypy 是「编译期」工具，这正是它能与 pytest（运行期）互补的原因；③ **结构类型 Protocol vs 名义类型**：Java/C++ 要求「显式声明实现了某接口」，Python 的 `Protocol` 只要「对象长这样（有对应方法签名）」就兼容——鸭子类型的静态化表达（ex05 的 `Formatter`）。`strict` 模式（`disallow_untyped_defs` 等，project 已开）把「每个函数都必须有注解」变成强制，是工程化的落点。

### 4.6 ruff 的 AST 静态分析

ruff 与 mypy 同属「静态分析」，但管的是**风格与明显错误**而不是类型：它把源码解析成 **AST（抽象语法树）**，每条规则就是一个「树形模式匹配器」——`F401 未使用导入` 匹配「import 语句 + 名字从未出现在后续节点」、`E722 裸 except` 匹配「`except` 节点没有异常类型」、`I001 导入顺序` 比较 import 语句的字母序。因为只做语法层分析、不做类型推断，ruff 比 mypy 快得多（Rust 实现 + 单遍遍历，毫秒级），这也是「lint 每条提交都跑、mypy 可以慢一点」的分工依据。`--fix` 能自动修复机械性问题（排序、未用导入删除），把「人工评审」留给真正需要判断的规则。

### 4.7 质量门禁的流水线视角

把 3.1~3.6 的工具串起来看，本阶段真正的产物是一条**分层门禁流水线**：本地开发时 `ruff check`（毫秒级，即时反馈）→ 提交前 pre-commit 钩子（强制跑 lint + 格式 + 类型）→ 云端 CI（装依赖、多 Python 版本矩阵、完整测试 + 覆盖率报告）→ 合入主分支。每层都在「更晚、更贵」的位置兜底：lint 抓风格、mypy 抓类型、pytest 抓行为、CI 保证「换台机器结果一样」。这条流水线就是「可靠、可维护」的制度载体——**单靠自觉的代码质量是不可维护的，把检查自动化才是工程**（roadmap 必会概念「格式化和 lint 应自动化」）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 单元测试（工具函数、数据处理函数） | pytest 断言 + 异常测试 + 参数化（ex01、ex04、练习 1/4） |
| 测试数据组织与共享（多用例共用前置） | fixture 作用域 + 依赖注入 + conftest（ex02、练习 2、project） |
| 外部依赖隔离（网络 API、时钟、随机） | mock 的 patch / MagicMock / side_effect（ex03、练习 3） |
| 覆盖率度量（CI 报告、验收门槛） | trace / pytest-cov、语句覆盖语义（ex04、练习 4、project） |
| 类型安全与重构保障（大改不踩雷） | 类型注解 + mypy 静态检查（ex05、练习 5、project） |
| 代码风格统一（团队协作零争议） | ruff / black + pyproject.toml（ex06、project） |
| 提交前门禁（把检查制度化） | pre-commit 钩子（project 配置示例） |
| 云端持续集成（任何提交都过同一套门禁） | GitHub Actions CI（project 的 ci.yml） |

**不适合此阶段的事项**：

- 并发与异步代码的测试（pytest-asyncio、多线程/多进程下的测试）：ph14 并发、并行与异步阶段（roadmap 第 14 节，目录待建）
- 生产部署与平台级 DevOps（Docker 化、监控告警、流水线平台运维）：ph16 部署与 DevOps 阶段（roadmap 第 16 节，目录待建）
- 数据分析结果的正确性验证（pandas 透视表、可视化校验）：ph09 数据分析阶段
- 大型系统的契约测试、端到端测试体系、测试金字塔全量落地：超出本路线的阶段划分，属于团队工程实践，不在本阶段展开

**与其他语言同类机制的对比**（一句话级，为 analysis/ 与 Tenet 合成积累素材）：Go 把 `testing` 包与 `go test` 内置进语言与工具链（测试即一等公民），Rust 用 `cargo test` + 属性宏把测试与模块内联、并内置 `cargo clippy` 做 lint；Java 的 JUnit 生态成熟但测试靠断言库 + 第三方工具拼装，JS 的 Jest 内置 mock 与覆盖率、开箱即用。Python 的独特之处是 **pytest 作为「第三方但事实标准」的框架 + 原生 assert 的低摩擦 + mock/typing 进标准库**——工具链不是语言内置（如 Go/Rust），但生态把它固定成了默认——「谁写测试、怎么写测试」在 Python 里由生态公约决定，这正是本阶段把门禁制度化的原因。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条运行。验证环境：Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 + mypy 1.17.1 + black 25.9.0 + requests 2.32.5（全部本机已装并实测）。全部示例**离线可跑**：ex01~ex04 的临时文件由 pytest 的 `tmp_path` fixture 自动创建并清理，ex05/ex06 的运行产物写到系统临时目录（`tempfile.mkdtemp`）——运行后用 `git status` 可确认工作区干净；ex03 用 mock 替换 `requests.get`，从不真正联网。依赖状态：**pytest-cov 与 pre-commit 未安装**——覆盖率用标准库 `trace` 实测，pre-commit 只给配置示例（3.7、project）。

### 示例 1：pytest 基础（断言、异常、tmp_path、参数化初体验）

呼应 3.1/3.2/3.4：生产函数与测试函数同文件，覆盖正常断言、`pytest.raises` 异常断言、`tmp_path` 临时文件、参数化初体验。完整文件 `examples/ex01-pytest-basics.py`。

```python
# examples/ex01-pytest-basics.py —— pytest 基础（离线可跑，已验证）
def parse_score(line: str) -> tuple[str, int]:
    """解析 '姓名,成绩' 一行；格式非法或成绩越界（0~100）抛 ValueError。"""
    name, score = line.strip().split(",")
    s = int(score)
    if s < 0 or s > 100:
        raise ValueError(f"成绩越界: {s}")
    return name, s

@pytest.mark.parametrize("line,expected", [
    ("Alice,88", ("Alice", 88)),
    ("Bob,0", ("Bob", 0)),
    ("Carol,100", ("Carol", 100)),
])
def test_parse_score_parametrized(line, expected):
    assert parse_score(line) == expected
```

实测输出：`python3 -m pytest ex01-pytest-basics.py -q` → **10 passed**（3 基础断言 + 1 tmp_path + 参数化 3+3 组）。

### 示例 2：fixture 进阶（作用域、autouse、工厂、依赖注入）

呼应 3.2/4.2：session 级共享、autouse 自动生效、工厂模式隔离数据、fixture 依赖注入四个机制一次演示。完整文件 `examples/ex02-fixture-scope.py`。

```python
# examples/ex02-fixture-scope.py —— fixture 进阶（离线可跑，已验证）
@pytest.fixture
def data_file(tmp_path):
    f = tmp_path / "raw.csv"
    f.write_text("ts,vehicle,speed\n2026-09-01 10:00,EV-001,42.0\n", encoding="utf-8")
    return f

@pytest.fixture
def store(data_file):
    # 依赖 data_file：pytest 先建 data_file，再把它注入这里的参数
    s = TelemetryStore(data_file.parent / "store.jsonl")
    s.append("2026-09-01 10:00", "EV-001", 42.0)
    return s

def test_store_injected(store):
    assert store.count() == 1
    assert store.vehicles() == {"EV-001"}
```

实测输出：`python3 -m pytest ex02-fixture-scope.py -q` → **7 passed**（session 共享 2 + autouse 1 + 工厂 2 + 依赖注入 2）。

### 示例 3：mock 外部依赖（网络请求隔离）

呼应 3.3/4.3：`patch` 替换 `requests.get`，覆盖成功、HTTPError、超时、side_effect 序列与「自动 mock 陷阱」五类路径。完整文件 `examples/ex03-mock.py`。

```python
# examples/ex03-mock.py —— mock 外部依赖（离线可跑，已验证 —— mock 后不会真的发网络请求）
def test_http_error():
    resp = fake_response(status=404, error=requests.exceptions.HTTPError("404 Client Error"))
    with patch("requests.get", return_value=resp):
        with pytest.raises(requests.exceptions.HTTPError):
            fetch_speed("EV-002")

def test_timeout():
    with patch("requests.get", side_effect=requests.exceptions.ConnectTimeout("timeout")):
        with pytest.raises(requests.exceptions.ConnectTimeout):
            fetch_speed("EV-003")
```

实测输出：`python3 -m pytest ex03-mock.py -q` → **6 passed**（成功 2 + HTTPError 1 + 超时 1 + side_effect 序列 1 + 自动 mock 陷阱 1），全程不发真实请求。

### 示例 4：参数化测试 + 覆盖率

呼应 3.4/4.4：边界值参数化铺满四档分支，`trace` 实测语句覆盖率。完整文件 `examples/ex04-parametrize.py`。

```python
# examples/ex04-parametrize.py —— 参数化 + 覆盖率（离线可跑，已验证）
@pytest.mark.parametrize("text", ["", "abc", "12.5", "12.5 km/h extra"])
def test_parse_reading_invalid(text):
    with pytest.raises(ValueError):
        parse_reading(text)
```

实测输出：`python3 -m pytest ex04-parametrize.py -q` → **14 passed**；本模块覆盖率 **100%**（trace 实测：25 个可执行行全命中）。

### 示例 5：类型注解 + mypy 干净版

呼应 3.5/4.5：dataclass、联合类型、Protocol 的完整注解版本，mypy 零错误。完整文件 `examples/ex05-mypy.py`。

```python
# examples/ex05-mypy.py —— 类型注解 + mypy（离线可跑，已验证）
def avg_speed_by_vehicle(rows: list[VehicleTelemetry]) -> dict[str, float]:
    """按车辆分组求平均速度；空输入返回空 dict。"""
    speeds: dict[str, list[float]] = {}
    for r in rows:
        speeds.setdefault(r.vehicle_id, []).append(r.speed)
    return {vid: sum(v) / len(v) for vid, v in speeds.items()}
```

实测输出：`mypy ex05-mypy.py` → `Success: no issues found in 1 source file`；`python3 ex05-mypy.py` 运行输出 3 行：`EV-001,42.0,88.0` / `{'EV-001': 48.5, 'EV-002': 30.0}` / `['EV-001: 42.0 km/h']`。

### 示例 5b：故意出错的类型错误（仅供 mypy 演示）

呼应 3.5/4.5：4 处类型错误供 mypy 逐个报错演示，**请勿直接运行**（会抛 AttributeError）。完整文件 `examples/ex05b-mypy-bugs.py`。

```python
# examples/ex05b-mypy-bugs.py —— 故意出错示例（类型错误版）：仅供 mypy 检查演示，请勿直接运行
def main() -> None:
    x: str = add(1, 2)              # 错误 1: assignment —— int 赋给声明为 str 的变量
    print(x)
    print(speed_label(Vehicle("EV-001", 42)))
    v = Vehicle("EV-002", 30.0)
    print(v.speed.upper())          # 错误 3: attr-defined —— float 没有 upper 方法
    total = total_speed([v])
    print(total, add("1", 2))       # 错误 4: arg-type —— str 传给声明为 int 的参数
```

实测输出：`mypy ex05b-mypy-bugs.py` → **Found 4 errors**（assignment / incompatible types / attr-defined / arg-type 各 1，故意出错）。

### 示例 6：ruff 干净版（lint + 格式双通过）

呼应 3.6：按 `examples/pyproject.toml` 配置（line-length 100、select E/F/I/UP/B），lint 与格式双通过。完整文件 `examples/ex06-ruff.py`。

```python
# examples/ex06-ruff.py —— ruff 配置 + 干净代码（离线可跑，已验证）
def write_report(rows: list[dict[str, str]], out: Path) -> None:
    if not rows:
        raise ValueError("空数据不生成报表")
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
```

实测输出：`ruff check ex06-ruff.py` → `All checks passed!`；`ruff format --check ex06-ruff.py` → `1 file already formatted`；运行输出合并后行数 2、报表 3 行（`EV-001,42.0,87.5` 为重复 id 合并后的最新电量）。

### 示例 6b：故意出错的 lint 违规（仅供 ruff 演示）

呼应 3.6：6 处 lint 违规对应 I001/F401/F821/F841/E722/E501，**请勿直接运行**（会 NameError）。完整文件 `examples/ex06b-ruff-bad.py`。

```python
# examples/ex06b-ruff-bad.py —— 故意出错示例（lint 违规版）：仅供 ruff check 演示，请勿直接运行
import sys          # I001: import 顺序错（isort 要求字母序，sys 应在 os 之后）
import os
import json         # F401: 未使用的导入

    except:                         # E722: 裸 except —— 连 KeyboardInterrupt 一起吞掉
        return None

    print(undefined_name)           # F821: 未定义名称（运行时会 NameError）
```

实测输出：`ruff check ex06b-ruff-bad.py` → **Found 6 errors**（I001 导入顺序 / F401 未使用导入 / F821 未定义名称 / F841 未使用变量 / E722 裸 except / E501 行超长，故意出错）。

## 7. 总结

### 关键要点

1. **pytest 是 Python 工程测试主力**（必会概念）：`test_` 约定零配置收集、原生 `assert` + 断言重写（4.1）、`pytest.raises` 断言异常、`tmp_path` 隔离临时文件
2. **fixture 是依赖注入**：scope 决定共享粒度（function/session）、autouse 免声明生效、`yield` 分割 setup/teardown、fixture 可以依赖 fixture（3.2/4.2）
3. **mock 隔离外部依赖**（必会概念）：`patch` 替换使用处的名字、`MagicMock` 自动模仿但要显式配置返回值（防假阳性）、`side_effect` 模拟错误与序列（3.3/4.3）
4. **参数化让边界值可枚举**：一组数据一个独立用例，失败精确到数据组；覆盖率是「测了多少」不是「对不对」——100% 不等于没 bug（3.4/4.4）
5. **类型注解提升可维护性**（必会概念）：`@dataclass`、`X | None`、`Protocol`；mypy 静态检查把类型错误挡在运行之前，`Any` 是债不是解药（3.5/4.5）
6. **格式化和 lint 应自动化**（必会概念）：ruff 一条命令 lint + 格式、black 输出唯一、配置进 `pyproject.toml`、`--check` 模式供 CI（3.6）
7. **门禁要制度化**：pre-commit 管提交前、CI 管提交后，本地命令（`ruff check . && mypy . && pytest`）与云端流水线等价（3.7/4.7）

### 阶段验收清单

- [ ] 能写 pytest 测试（对应 roadmap「能写 pytest 测试」）：断言、`pytest.raises`、`tmp_path`、参数化四件套随手可用
- [ ] 能运行 ruff/black/mypy（对应 roadmap「能运行 ruff/black/mypy」）：三条命令各知道查什么、报错能看懂规则码（E/F/I/UP/B、assignment/attr-defined 等）
- [ ] 能统计覆盖率（对应 roadmap「能统计覆盖率」）：`trace` 命令能跑、能解释语句覆盖率语义、知道 100% 的边界
- [ ] 能用 fixture 组织测试数据、用 mock 隔离外部依赖，并说清每个 fixture 的 scope 与依赖关系
- [ ] 能说清「覆盖率 100% ≠ 没有 bug」「mock 假阳性」「Any 是债」三个认知陷阱
- [ ] 能独立跑通 8 个示例并解释每个的实测数字（第 6 章），能对照 project 说出门禁流水线各层管什么

### 跨语言对比：测试与工程质量

| 维度 | Python | Go | Rust | Java | JavaScript |
|------|--------|----|------|------|------------|
| 测试框架 | pytest（第三方事实标准） | `testing` 包内置 | `cargo test` 内置 | JUnit 生态 | Jest（内置 mock/覆盖率） |
| 断言风格 | 原生 assert + 断言重写 | `t.Errorf`/`t.Fatal` | `assert_eq!` 宏 | AssertJ 等断言库 | expect/toBe 匹配器 |
| 类型检查 | mypy 渐进式（外部工具） | 编译器静态类型内置 | 编译器 + borrow checker | javac 编译器 | TypeScript（语言超集） |
| lint/格式 | ruff/black（外部生态） | gofmt 官方内置 | clippy/rustfmt 官方内置 | Checkstyle/Spotless | ESLint/Prettier |
| 门禁自动化 | pre-commit + CI（生态拼装） | 官方工具链 + CI | cargo 子命令 + CI | Maven/Gradle 插件 | husky + CI |

一句话：Go/Rust 把「测试、格式化、lint」内建进官方工具链（零选择成本），Python/Java/JS 靠生态公约固定默认——**pytest/ruff 的事实标准地位，就是 Python 版的「内置」**（为 analysis/ 与 Tenet 合成积累素材：一门语言若想降低工程质量门槛，把测试与 lint 内建是 Go/Rust 给的最直接启示）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。对应 roadmap「练习」小节（工具函数测试、数据处理测试、mock 外部接口），练习 5 补「学习内容」里的类型注解/mypy 门禁——工程质量的另一半，完成 5 题后继续：

- 工具函数测试（★）：字符串/文本工具四函数 + 参数化 + tmp_path JSON 往返（提示：`pytest.raises`；参考实现 9 个用例）
- fixture 组织测试数据（★★）：TaskStore 的 empty/prefilled/session/autouse 四类 fixture（提示：`scope="session"` 计数断言 1；参考实现 8 个用例）
- mock 外部接口（★★）：TelemetryFetcher 的成功/错误/超时路径 + `assert_called_once_with` 含 timeout（提示：`patch.object` 验证 `fetch_batch` 复用单条逻辑；参考实现 7 个用例）
- 参数化 + 覆盖率（★★★）：速度四档边界 + 非法读数 + 续航计算的参数化全覆盖，trace 实测写进验证块（提示：0/30/120 三个分界点两侧；参考实现 18 个用例、100%）
- 类型注解 + mypy + ruff（★★★）：InventoryItem 数据类全注解 + 三样门禁全绿（提示：`InventoryItem | None` 联合类型；参考实现 8 个用例、mypy Success、ruff All checks passed）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**带测试与质量门禁的遥测数据处理库（telemetry-stats）**——CSV 解析清洗 → 按车辆分组统计 → CSV 报表 + 文本汇总，24 个 pytest 用例 + ruff/mypy/black 全绿 + `--demo` 离线自检，并把门禁搬上 pre-commit 配置与 GitHub Actions CI（对应 roadmap「推荐项目」第一个「带测试的数据处理库」；另一个「FastAPI 测试模板」作为扩展方向）。建议完成练习后再动手，尤其练习 4/5（覆盖率与类型门禁的缩小版）。

- [ ] 完成 exercises/ 全部 5 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`python3 -m pytest` → 24 passed；`ruff check .`、`mypy telemetry_stats cli.py`、`black --check .` 全绿；`python3 cli.py --demo` 自检通过）

### 下一阶段

**ph14+（roadmap 第 14 节，目录待建）**：本阶段是当前学习路线的最后一个已建目录阶段，后续可深入**并发、并行与异步**方向——threading/multiprocessing/asyncio、concurrent.futures、aiohttp/httpx async、异步 FastAPI；测试体系里「怎么测并发与异步代码」（pytest-asyncio、多线程/多进程下的测试策略）也留到那里——ph13 的 mock/参数化/覆盖率心智，正是 ph14 验证异步正确性的起点；在此之前可先按推荐学习顺序巩固 ph12 自动化脚本阶段与本阶段的练习与项目。
