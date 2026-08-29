# Python 第三方库阶段

> 面向自动化、数据分析、Web 服务方向，本阶段掌握 requests/httpx、numpy/pandas、matplotlib、FastAPI、pytest 等常用生态，快速完成"请求 API、抓网页、分析 CSV、画图、写接口"的工程任务，让"选对库、会用库"成为解决问题的第一能力。

## 1. 概述

Python 第三方库阶段的目标是：**面对工程任务能先选对库、再读文档、快速落地——用 requests/httpx 请求 API，用 numpy/pandas 处理与分析数据，用 matplotlib 画图，用 FastAPI 写接口，用 pytest/ruff 保障质量**。这一阶段把 ph07 的"环境与依赖管理"升级为"生态驾驭能力"——**会用库、会选库、会评估依赖成本，是数据分析（ph09）、Web 后端（ph10）、测试（ph13）等所有后续阶段共同的地基**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| HTTP 客户端 | `requests`（同步）、`httpx`（同步 + 异步）、`aiohttp`（异步） |
| 网页抓取 | `beautifulsoup4`、`selenium`、`playwright` |
| 数值与表格 | `numpy`、`pandas`、`polars`、`openpyxl` |
| 可视化 | `matplotlib`、`plotly`、`seaborn` |
| Web 框架 | `FastAPI`、`Flask`、`Django` |
| 测试 | `pytest`（fixture、参数化、断言） |
| 质量工具 | `ruff`、`black`、`mypy` |
| 选型与工程 | 选库原则、依赖成本、质量工具自动化 |

**范围边界**：本阶段承接 ph07 虚拟环境与包管理阶段，聚焦"选库 + 用库"本身。不涉及数据分析深入（ph09：缺失值处理、时间序列、透视表——本阶段 numpy/pandas 只做到能读 CSV、筛选、分组统计、出图为止）、Web 后端深入（ph10：认证鉴权、数据库 ORM、中间件）、AI/ML（ph15）；`selenium`/`playwright` 与 `aiohttp` 本阶段只做选型与最小用法，大规模并发采集与异步深入在 ph14。

## 2. 来源与演变

HTTP 客户端从标准库 `urllib` 起步，但 API 繁琐、连接管理原始。2011 年 **requests**（"HTTP for Humans"）以极简 API 成为事实标准，底层基于 **urllib3** 的连接池；2015 年 **aiohttp** 为 asyncio 生态提供异步客户端；2019 年 **httpx** 融合两者——同一套 API 同时提供同步与异步模式、原生支持 HTTP/2，成为现代新项目的首选。网页抓取侧，**Beautiful Soup**（2004）专注 HTML 解析，**selenium**（2004）用浏览器驱动（WebDriver）做自动化，2020 年微软的 **playwright**（源自 Puppeteer）以"自带浏览器、API 现代"成为新一代方案。

数值与数据生态源于学术计算：**numpy** 由 1995 年的 Numeric 与 2001 年的 Numarray 于 2006 年合并而来，成为 Python 数值计算地基；**pandas**（2008，Wes McKinney）在 numpy 之上提供带标签的 DataFrame，把"数据清洗与分析"变成几行代码；2020 年 **polars**（Rust 编写）以惰性求值与多核并行挑战 pandas 的性能天花板；**openpyxl** 则是 Excel xlsx 读写的标准工具。可视化上，**matplotlib**（2003）是底层绘图标准，**seaborn**（2012）在其上提供统计图表，**plotly**（2012）提供浏览器交互图表。

Web 侧从 **Django**（2005，"全家桶"）到 **Flask**（2010，微框架）再到 **FastAPI**（2018，Sebastián Ramírez）：FastAPI 基于 Starlette 与 Pydantic，类型驱动、自动生成 OpenAPI 文档、async 原生，是 2020 年代增长最快的 API 框架。测试与质量工具链同样在整合：**pytest**（2004，源自 py.test）以原生 assert + fixture + 参数化成为事实标准；**black**（2018）终结格式之争；**mypy**（2012，Guido 主导）带来渐进式类型检查；2022 年 **ruff**（Rust 编写）以一条命令整合 lint + format + import 排序，速度比 flake8 快数十倍，宣告"flake8/black/isort 各管一段"的工具链碎片化时代结束。

| 时间 | 里程碑 |
|------|-------|
| 2004 | pytest 前身 py.test 与 Beautiful Soup 诞生 |
| 2006 | numpy 1.0（Numeric 与 Numarray 合并） |
| 2008 | pandas 发布（Wes McKinney） |
| 2011 | requests 发布——"HTTP for Humans" |
| 2018 | FastAPI 与 black 发布 |
| 2019 | httpx 发布——同步/异步双模式 + HTTP/2 |
| 2020 | polars 与 playwright 发布 |
| 2022 | ruff 发布——Rust 一站式 lint + format |

## 3. 语法与参数

### 3.1 requests 与 httpx：同步/异步 HTTP 客户端选型

```python
import requests

resp = requests.get("https://httpbin.org/json", timeout=10)   # 需联网
print(resp.status_code)                                    # 200
print(resp.json()["slideshow"]["title"])                   # 自动解析 JSON

import httpx

with httpx.Client(timeout=10) as client:                   # 同步客户端
    r = client.get("https://httpbin.org/json")
    print(r.status_code)

async def main():
    async with httpx.AsyncClient(timeout=10) as client:    # 异步客户端
        r = await client.get("https://httpbin.org/json")
        return r.json()
```

| 维度 | requests | httpx | aiohttp |
|------|----------|-------|---------|
| 同步 / 异步 | 仅同步 | 同步 + 异步（同一 API） | 仅异步 |
| 底层 | urllib3 | httpcore | 自有（asyncio 原生） |
| HTTP/2 | 否 | 是 | 否 |
| 适用场景 | 脚本、自动化——默认首选 | 需要异步或双模式统一 | 纯 asyncio 生态、大量并发 |

要点：

- **同步和异步 HTTP 客户端不要混用**（roadmap 必会概念）：项目里要么全同步（requests 或 `httpx.Client`），要么全异步（`httpx.AsyncClient` / aiohttp）；混用会在异步代码里出现同步阻塞，事件循环被卡死——这是本阶段头号必会概念。
- **坑（requests 默认无超时）**：不传 `timeout` 会**无限等待**——上游挂起时脚本永久卡死；所有网络请求必须显式 `timeout=`（秒）。
- **选库原则**：优先成熟、维护活跃的库（roadmap 必会概念）——看 PyPI 下载量、GitHub 最近提交、文档质量、Python 版本支持；脚本/自动化用 requests，涉及异步或 HTTP/2 用 httpx，aiohttp 留给 ph14 的纯 asyncio 项目。

### 3.2 网页抓取：beautifulsoup4·selenium·playwright 选型

```python
import requests
from bs4 import BeautifulSoup

resp = requests.get("https://httpbin.org/html", timeout=10)   # 需联网
soup = BeautifulSoup(resp.text, "html.parser")
print(soup.title.get_text())               # 标题文本
for link in soup.find_all("a"):            # 全部链接
    print(link.get("href"))
print(len(soup.select("p")))               # CSS 选择器：统计 p 标签
```

| 库 | 类型 | 适用场景 | 备注 |
|----|------|---------|------|
| beautifulsoup4 | HTML 解析 | 数据已在 HTML 里（静态/服务端渲染） | 轻量首选 |
| requests + bs4 | 组合 | 大多数"GET 就能拿到"的页面 | 默认方案 |
| selenium | 浏览器自动化 | 模拟点击、登录、动态渲染 | 需版本匹配的 WebDriver |
| playwright | 浏览器自动化（新一代） | 同 selenium，环境更省心 | 自带浏览器（首次下载体积大） |

要点：

- 优先级：**先 requests + bs4，拿不到数据再上浏览器自动化**；抓取前遵守目标站点 robots.txt 与服务条款。
- **坑（selenium 环境依赖）**：selenium 要求浏览器与 WebDriver **版本匹配**，换机器/CI 常报 `WebDriverException: SessionNotCreated`；playwright 一条 `playwright install` 自带浏览器，无驱动匹配问题，但首次下载约百 MB。
- 解析优先 CSS 选择器 `soup.select("div.item > a")`；数据由 JS 动态渲染的页面 requests 拿不到，改用 playwright（本阶段会最小用法即可）。

### 3.3 numpy 数组基础（ndarray·广播·向量化）

```python
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
print(arr + 10, arr * 2)               # 向量化：整数组运算，无 for 循环
print(np.mean(arr), np.std(arr))       # 3.0 1.414...

m = np.arange(12).reshape(3, 4)        # 0..11 排成 3 行 4 列
print(m.shape, m.dtype)                # (3, 4) int64
print(m[1, 2], m[:, 1])                # 元素 / 整列切片

a = np.array([[1], [2], [3]])          # 形状 (3,1)
b = np.array([10, 20, 30])             # 形状 (3,)
print(a + b)                           # 广播成 (3,3)
```

要点：

- **向量化（vectorization）**：用数组表达式替代 Python 循环，性能差几十倍（原理见 4.2）；`np.arange`/`np.linspace`/`np.zeros`/`np.random.rand` 是常用构造器。
- **广播规则**：两个数组维度从右往左对齐，相等或其一为 1 才能扩展运算；`reshape` 前后元素个数一致，`-1` 可自动推断（`arr.reshape(-1, 4)`）。

### 3.4 pandas 入门（Series·DataFrame·读取·筛选·groupby）

```python
import pandas as pd

s = pd.Series([10, 20, 30], index=["a", "b", "c"])
print(s["b"])                              # 20

df = pd.DataFrame({
    "vehicle_id": ["V001", "V001", "V002", "V002"],
    "speed": [80, 95, 60, 72],
    "soc": [78.5, 76.0, 90.1, 88.4],
})
print(df.info())                           # 列类型与空值
print(df["speed"].mean())                  # 76.75

df2 = pd.read_csv("data.csv")              # 读 CSV（练习核心）
fast = df[df["speed"] > 70]                # 布尔筛选
print(fast)
print(df.groupby("vehicle_id")["speed"].mean())   # 分组统计
df.to_csv("out.csv", index=False)          # 写回，别带行号列
```

要点：

- **DataFrame 操作要关注索引**（roadmap ph09 必会概念，本阶段先建立意识）：筛选/groupby 后索引不连续或改变，`reset_index()` 恢复 0..n-1。
- **坑（pandas 索引陷阱）**：`df.iloc[5]` 按位置取第 6 行，`df.loc[5]` 按索引标签取——筛选后两者可能不是同一行；链式赋值 `df[df["speed"]>70]["soc"] = 0` 触发 SettingWithCopyWarning 且**不生效**，要改成 `df.loc[df["speed"]>70, "soc"] = 0`。
- 常用：`head()`/`describe()`/`value_counts()`/`sort_values()`；`to_csv(index=False)` 忘写会多出一列行号。

### 3.5 openpyxl 与 polars 简述

```python
import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["vehicle_id", "speed", "soc"])
ws.append(["V001", 80, 78.5])
wb.save("report.xlsx")                     # 生成 Excel

wb2 = openpyxl.load_workbook("report.xlsx")
print([c.value for c in wb2.active[1]])    # 读表头

import polars as pl

df = pl.read_csv("data.csv")
print(df.group_by("vehicle_id").agg(pl.col("speed").mean()))
```

| 库 | 定位 | 何时用 |
|----|------|--------|
| openpyxl | Excel xlsx 读写 | 生成/修改带格式的 Excel 报表 |
| pandas | 通用表格分析 | 绝大多数数据分析场景 |
| polars | 高性能 DataFrame（Rust） | 大数据量、多核并行、流式处理 |

要点：openpyxl 管"文件格式"，pandas/polars 管"分析"；**第三方库引入要考虑依赖成本**（roadmap 必会概念）——csv 小任务用标准库 `csv` 就好，pandas 会连带 numpy 引入几十 MB 依赖，polars 再快也不值得为小数据引入；本阶段认识 polars/openpyxl 基本用法即可，深入在 ph09/ph12。

### 3.6 matplotlib·plotly·seaborn 可视化选型

```python
import matplotlib
matplotlib.use("Agg")                      # 无显示环境（服务器/CI）也能出图
import matplotlib.pyplot as plt

x = [1, 2, 3, 4, 5]
y = [80, 95, 60, 72, 88]
plt.plot(x, y, marker="o")                 # 折线图
plt.xlabel("time"); plt.ylabel("speed")
plt.title("Speed Trend")
plt.savefig("trend.png", dpi=150)          # 保存文件
```

| 库 | 定位 | 适合 |
|----|------|------|
| matplotlib | 底层绘图库 | 精细控制、脚本出图、出版级图表 |
| seaborn | 统计图表（matplotlib 之上） | 分布、箱线图、热力图 |
| plotly | 交互式图表 | 浏览器交互、Dashboard、Jupyter |

要点：脚本画图**必须 `savefig()`**，`plt.show()` 在无显示环境会报错或挂起（示例 3 演示完整流程）；seaborn 是 matplotlib 的"统计皮肤"，`sns.boxplot`/`sns.histplot` 一行出统计图；**图表要服务结论**——先想清楚这张图回答什么问题。

### 3.7 FastAPI 快速上手（路由·Pydantic·async）

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Demo API")

class Car(BaseModel):                      # Pydantic：声明 + 校验 + 文档
    vehicle_id: str
    speed: float

cars: list[Car] = []

@app.get("/cars")
def list_cars():
    return cars

@app.post("/cars", status_code=201)
def add_car(car: Car):                     # 请求体自动校验
    cars.append(car)
    return car
```

```bash
pip install "fastapi[standard]"            # 含 uvicorn
uvicorn main:app --reload --port 8000      # 启动；浏览器开 http://127.0.0.1:8000/docs
```

| 框架 | 定位 | 特点 |
|------|------|------|
| FastAPI | 现代 API 框架 | 类型驱动、自动 OpenAPI 文档、async 原生 |
| Flask | 微框架 | 简单灵活、同步为主、生态老 |
| Django | 全家桶 | 内置 ORM/Admin/Auth，适合完整站点 |

要点：

- **Pydantic 负责数据校验和序列化**（roadmap ph10 必会概念，本阶段入门）：请求体类型不符自动返回 **422** 而非手工检查；模型同时生成 OpenAPI schema。
- **坑（FastAPI 同步阻塞 async）**：`async def` 路由里调用 `requests.get`（同步阻塞）会**卡死整个事件循环**——异步路由只能 await 异步操作；纯同步逻辑用普通 `def` 路由（FastAPI 自动丢进线程池）。
- 本阶段写接口练习用 FastAPI 就够；Flask/Django 只做了解（上表），深入在 ph10。

### 3.8 pytest 基础（fixture·断言·参数化）

```python
import pytest

def add(a, b):
    return a + b

def test_add():
    assert add(1, 2) == 3                  # 原生 assert，失败自动展开实际值

@pytest.fixture
def sample():
    return {"speed": 80, "soc": 78.5}      # fixture：每个用例独立的新对象

def test_fixture(sample):
    assert sample["speed"] == 80

@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3), (0, 0, 0), (-1, 1, 0),
])
def test_param(a, b, expected):
    assert add(a, b) == expected
```

```bash
pip install pytest
pytest -q                       # 运行当前目录全部测试
pytest -q test_demo.py -k add   # 按名称过滤
pytest --maxfail=1              # 第一个失败即停
```

要点：

- pytest 约定：文件 `test_*.py`、函数 `test_*`；**断言用原生 `assert`**，失败信息自动展开两侧实际值。
- fixture 替代 unittest 的 setup/tearDown，是"准备 + 清理"的声明式写法；`@pytest.mark.parametrize` 让一组数据生成一组独立用例（机制见 4.5）。
- **工程质量工具要自动化**（roadmap 必会概念）：测试、lint、格式检查都应一条命令可跑（如 `pytest && ruff check .`），并接入 CI（ph13 深入），而非靠自觉。

### 3.9 ruff·black·mypy 质量工具链配置

```toml
# pyproject.toml（承接 ph07）
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]   # 错误/未定义/导入排序/新语法/常见 bug

[tool.black]
line-length = 88

[tool.mypy]
python_version = "3.11"
```

```bash
pip install ruff black mypy
ruff check .       # lint：找问题
ruff format .      # 格式化（与 black 二选一，别混用）
black .            # 或 black 格式化
mypy main.py       # 类型检查
```

要点：

- **ruff 取代 flake8/black/isort 的工具链整合**：2022 年起的 Rust 一站式方案，`ruff check`（lint + 导入排序）与 `ruff format`（格式化）比旧工具快数十倍；black 与 `ruff format` 二选一，同一项目别混用。
- mypy 是**渐进式类型检查**：从 `--check-untyped-defs` 起步，再逐步开 `strict`；类型注解不写全，mypy 检查就没有意义。
- **坑（只装不跑）**：工具装了一直不执行等于没有——把 `ruff check . && pytest` 写进 README / pre-commit / CI，质量检查才算"自动化"。

## 4. 底层原理

### 4.1 requests vs httpx 的传输层（urllib3/HTTPX 连接池与 keep-alive）

requests 底层是 **urllib3**：它实现了**连接池（connection pool）**与 **keep-alive**。HTTP/1.1 支持长连接，urllib3 按 `(host, port)` 把空闲 TCP 连接分桶缓存，同主机后续请求直接复用已建立（含 TLS 握手完成）的连接，避免反复"三次握手 + TLS"的开销。每次裸调 `requests.get()` 都会新建连接并随手丢弃——**循环/批量请求务必用 `requests.Session()` 复用连接池**，性能差距可达数量级。httpx 的传输层是 **httpcore**：同样维护连接池（`httpx.Client()` 复用），并原生支持 **HTTP/2 多路复用**——一条连接并发多个请求流，这是它在"并发请求同一主机"场景胜过 requests 的核心原因。**坑**：`requests.Session` 不是线程安全的，多线程共享要加锁或每线程一个；`httpx.Client` 线程安全，但所有线程共享同一连接池，注意连接池上限配置。

### 4.2 numpy 的 C 扩展与向量化原理

numpy 的 **ndarray 是 C 语言实现的**：数据存放在一块**连续的同类型内存**里，元素不是 Python 对象而是裸 C 数值。Python 循环慢的本质：每个元素都是 PyObject（对象头 + 引用计数 + 类型分派），解释器逐条执行字节码。numpy 的向量化运算（如 `arr + 10`）把整个表达式**下沉为一层 C 循环**：一次遍历连续内存、零解释器开销，现代 numpy 还会用 **SIMD** 指令一次处理多个元素——这就是"差几十倍"的来源。**广播（broadcasting）**依赖 **strides（步长）** 机制：形状不同的数组通过扩展步长描述"逻辑形状"参与运算，不复制数据、不新建数组，几乎零成本；代价是广播结果仍是视图语义，写回时要留意（呼应 4.3 的视图问题）。

### 4.3 pandas 的索引对齐与复制/视图语义

pandas 建立在 numpy 之上，多了一层**标签索引（index / columns）**。关键机制是**索引对齐（index alignment）**：两个 Series/DataFrame 做运算时按标签自动对齐，缺失的位置填 **NaN**——好处是"按名字对数据"无需手工对齐；**坑**是运算会悄悄产生 NaN，`df1 + df2` 若索引不完全一致，结果里出现大量 NaN 却不报错。另一机制是**视图与副本（view vs copy）**：numpy 切片返回共享内存的视图，pandas 为安全起见多数操作返回副本，但 `df["col"]`、`df.loc[...]` 可能返回视图——**链式赋值** `df[df["a"]>1]["b"]=2` 是先取视图再赋值，第一次取值已返回副本，赋值落空并触发 SettingWithCopyWarning。规则：**要修改就用 `df.loc[条件, 列] = 值` 单步完成；要独立数据就显式 `.copy()`**；pandas 3.0 起 `copy_on_write` 成为默认，从根上缓解这类问题。

### 4.4 FastAPI 的 ASGI 与 Pydantic 校验流程

FastAPI 运行在 **ASGI（Asynchronous Server Gateway Interface）** 之上——WSGI 的异步后继，接口是一个接收 `(scope, receive, send)` 的异步可调用对象。**Uvicorn** 是 ASGI 服务器：解析 HTTP 请求构造 scope，调用 `app(scope, receive, send)`；**FastAPI**（基于 Starlette 路由）是 ASGI 框架。一次请求的完整流程：Uvicorn 解析 HTTP → Starlette 路由匹配 → FastAPI 解析路径/查询/请求体参数 → **Pydantic 校验**：请求体先经 `pydantic-core`（v2 用 Rust 实现）做类型转换与校验，失败立即返回 **422**（含结构化错误字段），成功则生成模型实例传入路由函数 → 返回值被序列化为 JSON 响应。于是"类型声明"同时承担了**校验规则、类型转换、OpenAPI schema** 三份工作。异步语义上，`async def` 路由直接跑在事件循环上，普通 `def` 路由被丢进线程池执行——所以**同步阻塞代码放进 `def` 路由才不卡事件循环**（呼应 3.7 的坑）。

### 4.5 pytest 的 fixture 作用域与收集机制

pytest 启动后先做**收集（collection）**：递归扫描目录下 `test_*.py` / `*_test.py`，收集 `test_*` 函数与 `Test*` 类中的 `test_*` 方法，组成测试节点树（session → module → class → function），随后逐个执行。**fixture** 的核心是**依赖注入**：测试函数参数名即声明依赖，pytest 查找同名 fixture（函数内定义 → 模块 → `conftest.py` 逐级向上）并按依赖图排序执行；fixture 可指定**作用域（scope）**：`function`（默认，每个用例重建）、`module`、`session`（整个会话只建一次，如数据库连接、浏览器实例）；`yield` 之前的代码是 setup、之后是 teardown。**参数化（parametrize）**在收集阶段为每组参数生成一个独立测试节点，失败互不影响。fixture 的"声明式准备 + 作用域 + teardown"正是它取代 unittest setUp/tearDown 的原因。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 请求 REST API 拿 JSON | requests/httpx + `timeout` + `resp.json()` + 错误处理 |
| 抓取网页提取数据 | requests + BeautifulSoup；动态页面用 playwright |
| 分析 CSV 数据 | pandas `read_csv` + 筛选 + `groupby` + `to_csv` |
| 生成图表与报表 | matplotlib `savefig`、openpyxl 写 xlsx |
| 数值计算 | numpy 向量化与广播 |
| 给工具写测试 | pytest fixture + 参数化 |
| 写最小 API 接口 | FastAPI + Pydantic + uvicorn |
| 代码质量检查 | ruff check/format、mypy |

**不适合此阶段的事项**：

- 数据分析建模深入（缺失值处理、时间序列、透视表、统计建模）：ph09 数据分析阶段
- 生产级 Web 开发（认证鉴权、SQLAlchemy、中间件、Nginx/容器部署）：ph10 Web 后端阶段、ph16 部署阶段
- 大规模并发采集（分布式爬虫、代理池、限速、反爬对抗）：ph14 并发阶段（本阶段 aiohttp 只做了解）
- AI/ML（模型训练、特征工程、模型评估）：ph15

## 6. 代码示例

### 示例 1：requests 请求 API（超时 + 错误处理 + JSON 解析）

呼应"请求 API"练习：封装一个带超时、状态检查、JSON 解析与错误分类的请求函数。

```python
# 依赖：pip install requests
import requests

def fetch_json(url: str, timeout: int = 10) -> dict:
    try:
        resp = requests.get(url, timeout=timeout)   # 显式超时，防挂起
        resp.raise_for_status()                     # 4xx/5xx 抛 HTTPError
        return resp.json()
    except requests.Timeout:
        raise RuntimeError(f"请求超时: {url}")
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP 错误: {e}")
    except requests.RequestException as e:
        raise RuntimeError(f"网络错误: {e}")

if __name__ == "__main__":
    data = fetch_json("https://httpbin.org/json")   # 需联网
    print(data["slideshow"]["title"])
    print(data["slideshow"]["author"])
```

要点：`raise_for_status()` 是"一行错误检查"；`resp.json()` 解析失败抛 `ValueError`；超时/HTTP/网络三类异常分开捕获，错误信息带 URL 方便排查。

### 示例 2：网页抓取（requests + BeautifulSoup 提取数据）

呼应"抓取网页"练习：抓一个页面，提取标题与全部链接。

```python
# 依赖：pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup

def fetch_title_and_links(url: str) -> tuple[str, list[str]]:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding          # 中文页面防乱码
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = sorted({a.get("href") for a in soup.find_all("a") if a.get("href")})
    return title, links

if __name__ == "__main__":
    title, links = fetch_title_and_links("https://httpbin.org/html")   # 需联网
    print("标题:", title)
    for link in links:
        print("链接:", link)
```

要点：中文页面先设 `resp.encoding = resp.apparent_encoding` 防乱码；`get_text(strip=True)` 清空白；链接用 set 去重。动态渲染页面此方案拿不到 → 换 playwright（3.2 选型）。

### 示例 3：CSV 数据分析（pandas 读取 + groupby 统计 + matplotlib 出图）

呼应"分析 CSV / 画图"练习：本示例离线可跑，先造一份模拟 CSV 再走完整分析链路。

```python
# 依赖：pip install pandas matplotlib
import matplotlib
matplotlib.use("Agg")            # 无显示环境也能 savefig
import matplotlib.pyplot as plt
import pandas as pd

# 1. 生成模拟车辆数据 CSV（真实场景换成 pd.read_csv("你的文件.csv")）
data = pd.DataFrame({
    "vehicle_id": ["V001"] * 4 + ["V002"] * 4,
    "time": [1, 2, 3, 4] * 2,
    "speed": [80, 95, 60, 72, 55, 63, 70, 68],
    "soc":   [78.5, 76.0, 74.2, 72.8, 90.1, 88.4, 86.0, 85.2],
})
data.to_csv("vehicle.csv", index=False)

# 2. pandas 读取 + 分组统计（对应"分析 CSV"练习）
df = pd.read_csv("vehicle.csv")
print(df.info())
avg = df.groupby("vehicle_id")[["speed", "soc"]].mean()
print(avg)

# 3. matplotlib 出图（对应"画图"练习）
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
for vid, g in df.groupby("vehicle_id"):
    ax[0].plot(g["time"], g["speed"], marker="o", label=vid)   # 折线图
avg.plot.bar(ax=ax[1])                                          # 柱状图
ax[0].set_title("Speed Trend"); ax[0].set_xlabel("time"); ax[0].legend()
plt.tight_layout()
plt.savefig("vehicle_analysis.png", dpi=150)
print("已保存 vehicle_analysis.png")
```

### 示例 4：FastAPI 接口（Pydantic 模型 + 一个 CRUD 路由）

呼应"写 FastAPI 接口"练习：保存为 `main.py`，`uvicorn main:app --reload` 启动；脚本直接运行则用 TestClient 自测。

```python
# 依赖：pip install "fastapi[standard]"（TestClient 需要 httpx，standard 已包含）
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Car API")

class Car(BaseModel):
    vehicle_id: str
    speed: float

cars: list[Car] = []

@app.get("/cars")
def list_cars():
    return cars

@app.get("/cars/{idx}")
def get_car(idx: int):
    if idx >= len(cars):
        return {"error": "not found"}, 404
    return cars[idx]

@app.post("/cars", status_code=201)
def add_car(car: Car):
    cars.append(car)
    return car

@app.put("/cars/{idx}")
def update_car(idx: int, car: Car):
    cars[idx] = car
    return car

@app.delete("/cars/{idx}")
def delete_car(idx: int):
    return cars.pop(idx)

if __name__ == "__main__":       # 免启动服务，用 TestClient 自测
    from fastapi.testclient import TestClient
    client = TestClient(app)
    print("POST 合法:", client.post("/cars", json={"vehicle_id": "V001", "speed": 80}).status_code)    # 201
    print("POST 非法:", client.post("/cars", json={"vehicle_id": "V001", "speed": "很快"}).status_code) # 422
    print("GET:", client.get("/cars").json())
    print("DELETE:", client.delete("/cars/0").status_code)   # 200
```

要点：Pydantic 模型同时管校验与文档；请求体类型不符自动 422（示例里 `"很快"` 不是 float）；`{...}, 404` 元组返回可自定义状态码；真实部署用 `uvicorn main:app --reload` 启动后访问 `/docs` 查看自动文档。

### 示例 5：pytest + ruff 质量工具（fixture + 参数化测试 + 配置示例）

呼应"能配置基础质量工具"验收：一个最小项目三件套——被测代码、测试文件、工具配置。

```python
# calc.py —— 被测代码
def add(a: int, b: int) -> int:
    return a + b

def parse_speed(raw: str) -> float:
    """解析速度字符串；非法输入抛 ValueError"""
    value = float(raw)
    if value < 0:
        raise ValueError("speed must be >= 0")
    return value
```

```python
# test_calc.py —— 测试
import pytest
from calc import add, parse_speed

@pytest.fixture
def speeds() -> list[float]:
    return [80.0, 95.0, 60.0]          # fixture：测试准备

@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3), (0, 0, 0), (-1, 1, 0),
])
def test_add(a, b, expected):
    assert add(a, b) == expected

def test_parse_speed_ok():
    assert parse_speed("80") == 80.0

def test_parse_speed_bad():
    with pytest.raises(ValueError):
        parse_speed("abc")

def test_speeds_fixture(speeds):
    assert len(speeds) == 3
```

```toml
# pyproject.toml —— ruff / mypy 配置
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
```

```bash
pip install pytest ruff mypy
pytest -q                # 6 个用例全过
ruff check .             # lint 零告警
ruff format .            # 格式化
mypy calc.py             # 类型检查通过
```

要点：参数化让"一组数据一组用例"；`pytest.raises` 断言异常；`ruff check . && pytest` 一键质量门禁，下一步接入 pre-commit/CI（ph13）。

## 7. 总结

### 关键要点

1. **优先选择成熟、维护活跃的库**：看 PyPI 下载量、GitHub 最近提交、文档质量、Python 版本支持（roadmap 必会概念）
2. **同步和异步 HTTP 客户端不要混用**：requests 或 httpx 二选一走到底，混用必然踩事件循环与阻塞的坑（roadmap 必会概念）
3. **网络请求一律显式 timeout**：requests 默认无超时，上游挂起脚本就永久卡死
4. **用向量化替代 Python 循环**：numpy/pandas 的数组表达式比 for 循环快数十倍（C 扩展 + SIMD）
5. **pandas 操作要关注索引**：区分 `iloc`/`loc`、groupby 后 `reset_index()`、改数据用 `df.loc[条件, 列]` 单步完成
6. **工程质量工具要自动化**：pytest + ruff（+ mypy）一条命令可跑，挂进 pre-commit/CI 而非靠自觉（roadmap 必会概念）
7. **第三方库引入要考虑依赖成本**：小任务标准库能解决就别引大库，引库要连带评估依赖树与体积（roadmap 必会概念）
8. **FastAPI 异步路由只 await 异步操作**：同步阻塞代码用 `def` 路由；请求体校验交给 Pydantic（自动 422）
9. **pytest 是测试事实标准**：原生 `assert` + fixture + 参数化，从本阶段起每个项目都带测试
10. **先选对库再写代码**：动手前按任务类型（请求/抓取/分析/画图/接口/测试）查选型表，再读官方文档

### 跨语言对比：生态与库选型

| 维度 | Python | Go | Java | JS/Node | Rust |
|------|--------|----|------|---------|------|
| HTTP 客户端 | requests / httpx | net/http / resty | OkHttp / HttpClient | axios / fetch | reqwest |
| 数据处理 | pandas / polars | gonum / goframe | Apache Commons CSV / Spark | arquero / csv-parse | polars / ndarray |
| 可视化 | matplotlib / plotly | go-echarts | ECharts / JFreeChart | ECharts / D3 | plotters |
| Web 框架 | FastAPI / Flask / Django | Gin / Echo | Spring Boot | Express / Fastify | axum / Actix-Web |
| 测试框架 | pytest | testing / testify | JUnit 5 | Jest / Vitest | cargo test / criterion |
| 质量工具 | ruff / black / mypy | gofmt / go vet | Checkstyle / SpotBugs | ESLint / Prettier / tsc | rustfmt / clippy |

### 阶段验收标准

- 能根据任务类型选择合适的库，并说清选型理由（对应 roadmap"能选择合适库"）
- 能阅读库官方文档（Quickstart + API Reference）完成任务，报错能回文档定位（对应 roadmap"能阅读库文档完成任务"）
- 能用 requests 请求 API、BeautifulSoup 抓网页、pandas 分析 CSV、matplotlib 画图、FastAPI 写最小接口（对应 roadmap 五项练习）
- 能写 pytest fixture + 参数化测试并跑通（对应 roadmap"工程质量工具要自动化"）
- 能配置 ruff/black/mypy 并运行检查，说明"工程质量工具要自动化"的价值（对应 roadmap"能配置基础质量工具"）
- 能解释"同步和异步 HTTP 客户端不要混用""第三方库引入要考虑依赖成本"两个必会概念

### 进入下一阶段前

确保能完成以下练习：

- 请求 API：用 requests 请求一个公开 API（如 httpbin.org 或 GitHub API），带 timeout + 错误处理 + JSON 解析（提示：先 `resp.raise_for_status()` 再 `.json()`；把请求封装成函数）
- 抓取网页：requests + BeautifulSoup 抓一个页面，提取标题与全部链接存成 CSV（提示：先看页面 HTML 结构再写 CSS 选择器；页面是 JS 渲染就换 playwright）
- 分析 CSV：pandas 读 CSV → `info()` 看类型 → groupby 统计 → `to_csv(index=False)` 输出（提示：筛选后注意索引，`reset_index()` 恢复）
- 画图：matplotlib 画折线图 + 柱状图并 `savefig`（提示：脚本里先 `matplotlib.use("Agg")` 防无显示环境报错）
- 写 FastAPI 接口：Pydantic 模型 + GET/POST 路由，`uvicorn main:app --reload` 启动，浏览器打开 `/docs` 验证（提示：类型不符应返回 422；`async def` 路由里别用 `requests.get`）
- 配置质量工具：给上面的项目加 pytest（fixture + 参数化）与 ruff，`pytest && ruff check .` 一键全绿（提示：把命令写进 README，下一步接入 pre-commit）

### 推荐项目

- **API 请求工具**：requests + argparse + logging 合体——支持 URL/参数/Headers 配置、超时与重试、错误分类输出、结果存 JSON/CSV，把 ph06 的 CLI 与日志能力用在真实 HTTP 场景（呼应 roadmap"API 请求工具"）
- **网页数据采集器**：给一组 URL，requests + BeautifulSoup 提取结构化字段（标题、链接、表格数据），清洗后存 CSV，pytest 覆盖提取函数，ruff 保持整洁（呼应 roadmap"网页数据采集器"）

### 下一阶段

**数据分析阶段**（ph09-data-analysis，文档规划中）—— NumPy/Pandas 深入、数据清洗、时间序列、可视化报告。
