# Python 语言学习 Roadmap

> 面向自动化、数据分析、Web 服务、AI 原型和车联网数据平台，重点建立快速解决实际问题的能力。

## 1. Python 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标

能写简单 Python 程序，理解解释器、脚本和基础语法。

### 学习内容

- Python 安装与解释器
- 缩进（Python 的语法规则）
- print、变量、注释
- int、float、bool、str、None
- 字符串操作（f-string、常用方法）
- 列表（list）与切片
- 输入输出、条件判断、循环
- 函数基础

### 必会概念

- Python 是动态类型语言
- 缩进是语法的一部分
- 变量名绑定对象而不是保存固定类型
- 可读性优先

### 示例

```python
name = "Python"
age = 30
print(f"Hello {name}, age={age}")
```

### 练习

- 猜数字游戏
- 成绩等级判定
- 词频统计
- 九九乘法表
- 简单命令行脚本

### 阶段验收

- 能独立运行脚本
- 能用条件和循环解决基础问题
- 能写简单函数

### 推荐项目

- 成绩等级判断工具
- 命令行小脚本

## 2. 数据结构阶段

> 📖 详细展开版见 [ph02-data-structure/02-data-structure.md](./ph02-data-structure/02-data-structure.md)

### 目标

熟练使用 Python 最常用的数据结构。

### 学习内容

- list、tuple、dict、set
- 切片、列表推导式、字典推导式
- 排序、遍历、去重
- 嵌套数据结构

### 必会概念

- list 可变，tuple 通常不可变
- dict 保持插入顺序
- set 适合去重和集合运算
- 推导式要保持可读

### 示例

```python
user = {"name": "Alice", "age": 20}
user["city"] = "Shanghai"
print(user.get("name"))
```

### 练习

- list 管理成绩
- dict 做通讯录
- set 去重
- 统计词频

### 阶段验收

- 能按场景选择数据结构
- 能处理嵌套 dict/list
- 能写清晰推导式

### 推荐项目

- 购物车
- 通讯录

## 3. 函数与模块化阶段

> 📖 详细展开版见 [ph03-func-module/03-func-module.md](./ph03-func-module/03-func-module.md)

### 目标

能把代码拆成函数、模块和包。

### 学习内容

- 函数定义、参数、返回值
- 默认参数、关键字参数
- args、kwargs、lambda
- 作用域、模块导入、包结构

### 必会概念

- 函数应只承担清晰职责
- 可变默认参数是常见坑
- 模块用于组织可复用代码
- 入口脚本和库代码要分离

### 示例

```python
def add(a: int, b: int) -> int:
    return a + b
```

### 练习

- 数学工具模块
- 字符串工具模块
- 文件处理模块
- 拆分通讯录程序

### 阶段验收

- 能设计函数参数和返回值
- 能组织多文件项目
- 能避免可变默认参数问题

### 推荐项目

- CLI 工具
- 工具函数库

## 4. 面向对象 OOP 阶段

> 📖 详细展开版见 [ph04-oop/04-oop.md](./ph04-oop/04-oop.md)

### 目标

理解类和对象，用对象组织复杂业务。

### 学习内容

- class、对象、属性、方法
- __init__、实例变量、类变量
- 继承、多态、封装
- property、staticmethod、classmethod
- 常见魔术方法

### 必会概念

- 类用于表达稳定的业务概念
- 组合通常比深继承更清晰
- 魔术方法让对象融入语言协议
- 封装是约束使用方式

### 示例

```python
class Motor:
    def __init__(self, speed):
        self.speed = speed

    def start(self):
        print(f"Motor start: {self.speed}")
```

### 练习

- 学生类
- 车辆类
- 传感器类
- 配置管理类

### 阶段验收

- 能设计清晰类职责
- 能使用继承和组合
- 能实现常见魔术方法

### 推荐项目

- 设备管理系统
- 配置管理器

## 5. 文件操作与异常处理阶段

> 📖 详细展开版见 [ph05-file-exception/05-file-exception.md](./ph05-file-exception/05-file-exception.md)

### 目标

能读写文件并处理错误。

### 学习内容

- open、with、encoding
- txt、csv、json、yaml、xml、log、excel
- try/except/finally
- 自定义异常

### 必会概念

- with 自动释放资源
- 文本文件要明确编码
- 异常要保留上下文
- 不要裸 except 吞掉错误

### 示例

```python
with open("data.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

### 练习

- 读配置文件
- 解析 CSV
- 读取 JSON
- 日志分析
- 批量重命名

### 阶段验收

- 能处理文件不存在和格式错误
- 能读写常见文本格式
- 能写清晰异常处理

### 推荐项目

- 日志分析工具
- 文件批处理工具

## 6. Python 标准库阶段

> 📖 详细展开版见 [ph06-stdlib/06-stdlib.md](./ph06-stdlib/06-stdlib.md)

### 目标

熟悉 Python 自带工具库，提高脚本和工程效率。

### 学习内容

- os、sys、pathlib、shutil
- json、csv、datetime、re
- logging、argparse、subprocess
- collections、itertools、functools
- threading、multiprocessing、asyncio、unittest

### 必会概念

- pathlib 优先于手写路径字符串
- logging 优先于 print 调试
- argparse 让脚本变成工具
- 标准库能解决大量基础问题

### 示例

```python
from pathlib import Path
for file in Path("data").glob("*.txt"):
    print(file.name)
```

### 练习

- 批量移动文件
- 正则提取日志
- 命令行参数工具
- subprocess 调命令

### 阶段验收

- 能熟练处理路径和文件
- 能写 CLI 参数
- 能使用 logging

### 推荐项目

- 批量重命名工具
- 日志提取工具

## 7. 虚拟环境与包管理阶段

> 📖 详细展开版见 [ph07-venv-packaging/07-venv-packaging.md](./ph07-venv-packaging/07-venv-packaging.md)

### 目标

能管理 Python 项目依赖和运行环境。

### 学习内容

- pip、venv
- requirements.txt
- pyproject.toml
- poetry、uv
- 开发依赖与运行依赖
- 项目隔离

### 必会概念

- 每个项目应有独立环境
- 依赖版本要可复现
- pyproject.toml 是现代项目入口
- 不要把虚拟环境提交进仓库

### 示例

```bash
python -m venv .venv
.venv\Scripts\activate
pip install requests
```

### 练习

- 创建虚拟环境
- 生成 requirements.txt
- 用 pyproject 管理项目
- 打包小工具

### 阶段验收

- 能隔离项目依赖
- 能复现安装环境
- 能说明运行和开发依赖

### 推荐项目

- Python 项目模板
- 可安装 CLI 包

## 8. 第三方库阶段

> 📖 详细展开版见 [ph08-third-party/08-third-party.md](./ph08-third-party/08-third-party.md)

### 目标

掌握常用生态，快速完成工程任务。

### 学习内容

- requests、httpx、aiohttp
- numpy、pandas、polars、openpyxl
- matplotlib、plotly、seaborn
- FastAPI、Flask、Django
- selenium、playwright、beautifulsoup4
- pytest、ruff、black、mypy

### 必会概念

- 优先选择成熟、维护活跃的库
- 同步和异步 HTTP 客户端不要混用
- 工程质量工具要自动化
- 第三方库引入要考虑依赖成本

### 示例

```python
import requests
resp = requests.get("https://example.com")
print(resp.status_code)
```

### 练习

- 请求 API
- 抓取网页
- 分析 CSV
- 画图
- 写 FastAPI 接口

### 阶段验收

- 能选择合适库
- 能阅读库文档完成任务
- 能配置基础质量工具

### 推荐项目

- API 请求工具
- 网页数据采集器

## 9. 数据分析阶段

> 📖 详细展开版见 [ph09-data-analysis/09-data-analysis.md](./ph09-data-analysis/09-data-analysis.md)

### 目标

能用 Python 做数据清洗、统计和可视化。

### 学习内容

- NumPy、Pandas DataFrame
- 数据读取、清洗、缺失值处理
- 分组统计、排序筛选、join
- 透视表、时间序列
- Matplotlib/Plotly 可视化

### 必会概念

- 数据清洗通常比建模更耗时
- DataFrame 操作要关注索引
- 分组统计是核心能力
- 图表要服务结论

### 示例

```python
import pandas as pd
df = pd.read_csv("data.csv")
print(df.describe())
print(df.groupby("vehicle_id")["speed"].mean())
```

### 练习

- 销售数据分析
- 车辆速度分析
- 电池数据分析
- CAN 日志统计

### 阶段验收

- 能读取并清洗 CSV
- 能做分组统计
- 能画趋势图和柱状图

### 推荐项目

- 车辆遥测分析脚本
- 电池健康分析报表

## 10. Web 后端开发阶段

> 📖 详细展开版见 [ph10-web-backend/10-web-backend.md](./ph10-web-backend/10-web-backend.md)

### 目标

能用 Python 写 API 服务。

### 学习内容

- HTTP、REST API
- FastAPI、Pydantic
- 路由、参数、JSON 响应
- 认证鉴权、JWT
- SQLAlchemy、Alembic
- Middleware、日志、错误处理
- OpenAPI 自动文档
- 模板渲染与静态文件（入门）
- 异步接口（入门）

### 必会概念

- Pydantic 负责数据校验和序列化
- API 层不应写复杂业务
- 异步接口要配套异步依赖
- OpenAPI 文档是交付物

### 示例

```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/ping")
def ping():
    return {"message": "pong"}
```

### 练习

- Todo API
- 登录注册
- 文件上传
- 设备管理 API

### 阶段验收

- 能启动 FastAPI 服务
- 能做参数校验
- 能连接数据库

### 推荐项目

- OTA 管理 API
- 设备数据上报 API

## 11. 数据库与缓存阶段

> 📖 详细展开版见 [ph11-database/11-database.md](./ph11-database/11-database.md)

### 目标

能开发完整业务系统。

### 学习内容

- SQL、SQLite、MySQL、PostgreSQL
- Redis
- SQLAlchemy、Alembic
- 事务、索引、迁移、连接池
- pymongo/motor 可选

### 必会概念

- SQL 基础比 ORM 更重要
- 迁移脚本让结构变更可追踪
- 事务保证一致性边界
- 缓存要有过期和失效策略

### 示例

```python
import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
```

### 练习

- 用户 CRUD
- 设备信息管理
- 车辆状态表
- Redis 缓存查询结果

### 阶段验收

- 能建表和 CRUD
- 能写迁移脚本
- 能设计基础缓存

### 推荐项目

- 设备管理后端
- 车辆状态存储服务

## 12. 自动化脚本阶段

> 📖 详细展开版见 [ph12-automation/12-automation.md](./ph12-automation/12-automation.md)

### 目标

用 Python 提升日常工作效率。

### 学习内容

- 文件批处理
- Excel 自动化
- 日志分析
- 接口测试
- 报表生成
- 爬虫、邮件发送、定时任务
- paramiko、fabric、schedule

### 必会概念

- 自动化脚本也要有日志和错误处理
- 重复任务应参数化
- 脚本要能安全重跑
- 输出结果要可审计

### 示例

```python
from pathlib import Path
for p in Path("logs").glob("*.log"):
    print(p.stat().st_size)
```

### 练习

- 批量整理日志
- 生成 Excel 报表
- 定时拉取接口
- 解析 CAN 日志

### 阶段验收

- 能把脚本写成可复用工具
- 能处理异常和日志
- 能参数化运行

### 推荐项目

- 自动报表生成器
- CAN 日志批处理工具

## 13. 测试与工程质量阶段

> 📖 详细展开版见 [ph13-testing-quality/13-testing-quality.md](./ph13-testing-quality/13-testing-quality.md)

### 目标

写出可靠、可维护的 Python 工程代码。

### 学习内容

- pytest、fixture、mock
- 参数化测试、覆盖率
- 类型注解、mypy
- ruff、black、pre-commit
- CI/CD

### 必会概念

- pytest 是 Python 工程测试主力
- 类型注解提升可维护性
- 格式化和 lint 应自动化
- mock 用于隔离外部依赖

### 示例

```python
def add(a: int, b: int) -> int:
    return a + b

def test_add():
    assert add(1, 2) == 3
```

### 练习

- 工具函数测试
- API 测试
- 数据处理测试
- mock 外部接口

### 阶段验收

- 能写 pytest 测试
- 能运行 ruff/black/mypy
- 能统计覆盖率

### 推荐项目

- 带测试的数据处理库
- FastAPI 测试模板

## 14. 并发、并行与异步阶段

> 📖 详细展开版见 [ph14-concurrency-async/14-concurrency-async.md](./ph14-concurrency-async/14-concurrency-async.md)

### 目标

处理 IO 密集和 CPU 密集任务。

### 学习内容

- threading
- multiprocessing
- asyncio
- concurrent.futures
- aiohttp/httpx async
- 异步 FastAPI

### 必会概念

- threading 适合 IO 密集
- multiprocessing 适合 CPU 密集
- asyncio 适合大量并发网络 IO
- 不要阻塞事件循环

### 示例

```python
import asyncio

async def work():
    await asyncio.sleep(1)
    print("done")

asyncio.run(work())
```

### 练习

- 并发下载文件
- 并发请求 API
- 多进程处理大文件
- 异步爬虫

### 阶段验收

- 能区分并发和并行
- 能选择线程/进程/异步
- 能避免阻塞异步代码

### 推荐项目

- 异步采集服务
- 并发日志处理器

## 15. AI / 机器学习阶段

> 📖 详细展开版见 [ph15-ai-ml/15-ai-ml.md](./ph15-ai-ml/15-ai-ml.md)

### 目标

进入 AI、数据建模和智能分析方向。

### 学习内容

- NumPy、Pandas、Matplotlib
- Scikit-learn
- PyTorch、Transformers
- 特征工程、模型评估
- 向量数据库、RAG
- 模型部署

### 必会概念

- 数据质量决定模型上限
- 先建立 baseline 再复杂化
- 训练、验证、测试集要分开
- RAG 需要关注检索质量

### 示例

```python
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
```

### 练习

- 房价预测
- 故障分类
- 传感器异常检测
- 文本分类
- 简单 RAG 问答

### 阶段验收

- 能完成基础建模流程
- 能评估模型效果
- 能说明数据泄漏风险

### 推荐项目

- 电池健康预测
- 日志异常检测

## 16. 部署与 DevOps 阶段

### 目标

把 Python 项目部署到真实环境。

### 学习内容

- Linux、Docker、Docker Compose
- Nginx、Gunicorn、Uvicorn
- Supervisor、systemd
- CI/CD
- 日志采集、监控、Prometheus、Grafana

### 必会概念

- 部署环境要可复现
- 配置与代码分离
- 服务要有健康检查
- 日志和监控是排障基础

### 示例

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 练习

- 部署 FastAPI 服务
- Docker Compose 启动服务和数据库
- Nginx 反向代理
- 配置 systemd

### 阶段验收

- 能构建镜像
- 能部署服务
- 能查看日志和指标

### 推荐项目

- FastAPI 部署模板
- 数据服务 Docker Compose

## 17. 高级 Python 阶段

### 目标

理解 Python 底层机制和高级特性。

### 学习内容

- 迭代器、生成器、装饰器
- 上下文管理器、描述符、元类
- GIL、垃圾回收、内存管理
- import 机制、dataclass、pydantic
- 协程原理、C 扩展、Cython

### 必会概念

- 生成器适合惰性处理大数据
- 装饰器适合横切逻辑
- GIL 影响 CPU 密集多线程
- 元类和描述符要谨慎使用

### 示例

```python
def count():
    for i in range(5):
        yield i
```

### 练习

- 计时装饰器
- 重试装饰器
- 上下文管理器
- 生成器处理大文件

### 阶段验收

- 能解释 GIL 影响
- 能写生成器和装饰器
- 能判断高级特性是否必要

### 推荐项目

- 流式日志处理器
- 可复用装饰器库

## 18. 车联网 / 数据平台 / 自动化方向阶段

### 目标

用 Python 支撑车联网数据分析、自动化测试和 AI 原型。

### 学习内容

- CAN 日志解析
- 车辆遥测数据处理
- 电池数据分析
- 故障诊断、报表生成
- 自动化测试平台
- FastAPI 数据服务
- AI 异常检测

### 必会概念

- Python 适合数据处理、工具和原型
- 车辆数据要关注时间序列和异常值
- 自动化测试要可重复和可审计

### 示例

```text
车辆日志 → Python 清洗 → Pandas 分析 → 报表 / API / 异常检测
```

### 练习

- CAN 日志解析器
- 车辆数据清洗工具
- OTA 测试报告生成
- MQTT 数据采集服务

### 阶段验收

- 能解析并清洗车辆数据
- 能生成报告或 API
- 能完成自动化测试闭环

### 推荐项目

- 车辆遥测 Dashboard
- 传感器异常检测模型

## 推荐学习顺序

```text
Python 基础语法
→ list / dict / set / tuple
→ 函数 / 模块
→ 文件操作 / 异常处理
→ 面向对象
→ 标准库
→ 虚拟环境 / pip / 项目结构
→ 第三方库
→ 测试 / 类型注解
→ 数据分析 / 自动化脚本
→ Web 后端 / FastAPI
→ 数据库 / Redis
→ 并发 / 异步
→ Docker / 部署
→ AI / 机器学习
→ 高级 Python
```

## Python 和 C / C++ / Rust / Go 的区别

| 方向 | C/C++ | Rust | Go | Python |
| --- | --- | --- | --- | --- |
| 学习曲线 | 中高 | 高 | 中低 | 低 |
| 执行速度 | 很快 | 很快 | 快 | 较慢 |
| 开发效率 | 中 | 中 | 高 | 很高 |
| 内存管理 | 手动/RAII | 所有权 | GC | GC |
| 类型系统 | 静态 | 静态 | 静态 | 动态 |
| 适合方向 | 底层/高性能 | 系统安全 | 后端/云原生 | 自动化/数据/AI/Web |

## 项目路线

### 初级项目

- 计算器
- 猜数字游戏
- 通讯录
- Todo CLI
- 批量重命名工具

### 中级项目

- CSV 数据分析工具
- 日志分析工具
- Excel 报表生成器
- Web API 服务
- 自动化测试工具

### 高级项目

- FastAPI 后端服务
- 异步爬虫系统
- 数据分析 Dashboard
- 自动化测试平台
- RAG 问答系统

### 车联网 / 智能电动车项目

- CAN 日志解析器
- 车辆数据分析平台
- 电池健康状态分析
- MQTT 数据接入服务
- 传感器异常检测模型

## 对你最推荐的 Python 路线

```text
Python 基础
→ 文件 / JSON / CSV
→ 正则表达式
→ Pandas
→ Matplotlib
→ 自动化脚本
→ pytest
→ FastAPI
→ PostgreSQL / Redis
→ MQTT / Kafka
→ Docker
→ AI 异常检测
→ 车辆数据平台
```

重点掌握：list、dict、function、class、file、exception、pathlib、json、csv、re、logging、argparse、pytest、dataclass、pydantic、pandas、numpy、matplotlib、FastAPI、SQLAlchemy、Redis、asyncio、Docker。
