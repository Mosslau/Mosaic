# Python Web 后端开发阶段

> 面向自动化、Web 服务、车联网数据平台方向，本阶段用 FastAPI + Pydantic + SQLAlchemy 写出能跑、能校验、能鉴权、能连数据库的 API 服务，让"用 Python 写后端接口"成为核心能力。

## 1. 概述

Python Web 后端开发阶段的目标是：**能用 Python 写 API 服务——用 FastAPI 定义路由与参数、用 Pydantic 完成数据校验和序列化、用 JWT 做认证鉴权、用 SQLAlchemy + Alembic 连接数据库并管理结构变更、用中间件与日志统一横切关注点**。这一阶段把 ph09 的数据分析能力接到"数据从哪来、给谁用"的接口层，同时把四个必会概念内化为习惯——**Pydantic 负责数据校验和序列化、API 层不应写复杂业务、异步接口要配套异步依赖、OpenAPI 文档是交付物**——这是数据库与缓存（ph11）、并发（ph14）、部署（ph16）与车联网数据平台方向共同的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| HTTP 与 REST API | 方法语义（GET/POST/PUT/DELETE）、状态码、资源式 URL、无状态 |
| FastAPI 路由与依赖注入 | `@app.get/post` 装饰器、路径/查询参数、`Depends`、子依赖与作用域 |
| Pydantic 模型 | 数据校验、序列化、嵌套模型、`Field` 约束、`model_dump`/`from_attributes` |
| 请求参数与响应 | 路径·查询·请求体·Header·Cookie、`response_model`、JSON 响应 |
| 认证鉴权 | JWT 签发与校验、OAuth2 基础、密码哈希存储、`Depends` 鉴权依赖 |
| SQLAlchemy 与 Alembic | ORM 模型、Session 会话、CRUD、`autogenerate` 迁移 |
| 中间件、CORS、日志与错误处理 | `@app.middleware`、跨域配置、`logging`、`HTTPException`、422/500 统一 JSON |
| OpenAPI 文档 | 自动生成的 `/docs`、`tags`/`summary`、作为交付物 |

**范围边界**：本阶段承接 ph09 数据分析阶段，聚焦"把业务能力暴露为 HTTP API"。不涉及数据库与缓存深入（ph11：SQL 优化、事务、索引、Redis 缓存）、并发与异步深入（ph14：大规模异步、消息队列）、部署运维（ph16：Nginx、Docker、CI/CD）；本阶段以同步 API 为主，`async def` 只做入门，数据库用 SQLite 起步。

## 2. 来源与演变

Web 后端在 Python 侧经历了"服务器协议 → 框架分化 → 类型驱动"三次演进。协议层：2003 年定义的 **WSGI（Web Server Gateway Interface）** 让应用与服务器解耦（应用是接收 `environ`、返回 `start_response` 的可调用对象），Flask/Django 都跑在 WSGI 上，但 WSGI 是同步的；2016 年 **ASGI（Asynchronous Server Gateway Interface）** 出现——应用变成接收 `(scope, receive, send)` 的异步可调用对象，同时支持 HTTP、WebSocket、SSE，**uvicorn** 是其参考实现，这是 FastAPI async 能力的协议地基。

框架侧从"全家桶"走向"类型驱动"：**Django**（2005）内置 ORM/Admin/Auth；**Flask**（2010）把 Web 退化为"一个函数 + 路由表"，简单灵活、同步为主；2018 年 **FastAPI**（Sebastián Ramírez，基于 **Starlette** 路由层与 **Pydantic** 数据层）用**类型注解**同时驱动参数解析、数据校验、OpenAPI 文档生成，原生支持 `async def`，成为 2020 年代增长最快的 API 框架。数据层同期整合：**SQLAlchemy**（2005，Mike Bayer）演进到 2.0 的类型化 `Mapped` 风格；**Alembic**（2011）把"改表结构"变成可版本化的迁移脚本；**Pydantic** 2023 年发布 **v2**，用 Rust 重写核心（pydantic-core），校验性能提升数倍。认证侧，**JWT（JSON Web Token，RFC 7519）** 以"签名自包含、服务端无状态"成为 API 鉴权事实标准，**OAuth2** 的 password 流程为其提供标准接入形态。

| 时间 | 里程碑 |
|------|-------|
| 2003 | WSGI 定义（同步协议，Flask/Django 的地基） |
| 2005 | SQLAlchemy 发布（Mike Bayer） |
| 2010 | Flask 发布 |
| 2011 | Alembic 发布——迁移脚本可版本化 |
| 2016 | ASGI 定义（异步协议，支持 WebSocket） |
| 2018 | FastAPI 发布（类型驱动 + OpenAPI 自动文档） |
| 2023 | Pydantic v2——Rust 重写核心（pydantic-core） |

## 3. 语法与参数

### 3.1 HTTP 与 REST API 基础（方法·状态码·资源语义）

REST（Representational State Transfer）的核心是"**用 HTTP 方法操作资源**"：URL 只表示资源（名词），动词交给方法。写接口前先定好"资源 + 方法 + 状态码"契约。

```python
# pip install httpx——客户端视角验证接口契约
import httpx
r = httpx.get("http://127.0.0.1:8000/todos", timeout=10)
print(r.status_code, r.json())              # 200 [...]
r = httpx.post("http://127.0.0.1:8000/todos",
               json={"title": "学 FastAPI"}, timeout=10)
print(r.status_code)                        # 201 创建成功
```

要点：

- **URL 只放资源不放动词**：`POST /devices` 而非 `/create_device`；嵌套资源用路径层级 `/devices/{id}/telemetry`。
- **状态码即语义**：2xx 成功、4xx 客户端错误（400 参数错、401 未认证、404 不存在、422 校验失败）、5xx 服务端错误；GET 幂等、POST 非幂等、DELETE 用 204。
- **坑（动词化 URL 与状态码滥用）**：`/get_device` 是 REST 反模式；删除返回 200 + 大段 JSON 而非 204 也不规范——接口契约从第一天就按"方法 + 资源 + 状态码"设计。

### 3.2 FastAPI 路由与依赖注入（路由·Depends·子依赖）

FastAPI 用装饰器声明路由，用**类型注解**声明参数，用 **`Depends`** 做依赖注入（解析机制见 4.3）。

```python
# 依赖：pip install "fastapi[standard]"（含 uvicorn）
from fastapi import Depends, FastAPI
app = FastAPI(title="Demo API")
def require_token():                        # 依赖：普通函数即可
    return {"user": "demo"}
@app.get("/items")
def list_items(user: dict = Depends(require_token)):
    return {"items": [], "user": user}
@app.get("/items/{item_id}")                # 路径参数：类型注解驱动解析与校验
def get_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

要点：

- **路由按声明顺序匹配**：`/items/me` 必须声明在 `/items/{item_id}` **之前**，否则 `"me"` 会被当成 `item_id` 而 422。
- `Depends` 依赖每次请求解析并注入，可嵌套、可复用——鉴权、数据库会话是典型用法（见 3.6/3.7）。
- **API 层不应写复杂业务**（roadmap 必会概念）：路由函数只做"取参数 → 调业务 → 返回响应"，业务逻辑放 service 层——路由薄、易测试。

### 3.3 Pydantic 模型（校验·序列化·嵌套·Field 约束）

**Pydantic 负责数据校验和序列化**（roadmap 必会概念）：一个 `BaseModel` 子类同时承担**校验规则、类型转换、序列化、OpenAPI schema** 四份工作。

```python
from pydantic import BaseModel, Field, field_validator
class Battery(BaseModel):
    soc: float = Field(ge=0, le=100)        # 约束：0~100
    voltage: float = Field(gt=0)
class Vehicle(BaseModel):
    vin: str = Field(min_length=17, max_length=17)
    model: str
    battery: Battery                        # 嵌套模型自动递归校验
    @field_validator("vin")
    @classmethod
    def vin_upper(cls, v: str) -> str:
        return v.upper()                    # 校验时顺便清洗
v = Vehicle(vin="LVGBE40K5GG123456", model="EV-A",
            battery={"soc": 80.5, "voltage": 380})
print(v.model_dump())                       # 序列化（v1 的 .dict() 已改名）
```

要点：

- **校验失败自动返回 422**，错误结构化（`loc`/`msg`/`type`），无需手写 if——这是"能做参数校验"的核心体现。
- **坑（Pydantic v2 API 变化）**：`@validator` → `@field_validator`、`.dict()` → `model_dump()`、`class Config` → `model_config`、`orm_mode` → `from_attributes`——照抄 v1 旧教程会直接报错。
- **坑（宽松转换与共享默认值）**：默认宽松模式 `"1"` 会被静默转成 int 1，要严格用 `ConfigDict(strict=True)`；可变默认值必须 `Field(default_factory=list)`，写 `= []` 会让所有实例共享同一列表。
- 从 ORM 对象构造模型：`model_config = {"from_attributes": True}`（见 3.7、示例 4）。

### 3.4 请求参数（路径·查询·请求体·Header·Cookie）

FastAPI 按**类型注解 + 默认值**自动判断参数来源，`Header`/`Cookie`/`Body` 显式指定。

```python
from fastapi import Cookie, FastAPI, Header
from pydantic import BaseModel
app = FastAPI()
class Report(BaseModel):
    title: str
    rows: list[dict]
@app.post("/reports/{report_id}")
def create_report(report_id: int, body: Report,                  # 路径参数、请求体
                  verbose: bool = False,                         # 查询参数（带默认值）
                  user_agent: str | None = Header(None),         # Header：User-Agent
                  session: str | None = Cookie(None)):           # Cookie
    return {"report_id": report_id, "verbose": verbose,
            "body": body, "ua": user_agent, "session": session}
```

要点：

- 判定规则一句话：**路径里有 `{}` 的是路径参数；Pydantic 模型是请求体；其余带默认值的是查询参数**。
- `Header` 大小写不敏感、连字符转下划线：`User-Agent` → `user_agent`；`Query(alias=...)` 可映射别名。
- **坑（参数来源搞混）**：同一名字既想当查询参数又想当请求体字段会报"重复声明"——请求体字段必须包在模型里。

### 3.5 JSON 响应与响应模型（response_model·状态码）

FastAPI 自动把返回值序列化为 JSON；**`response_model` 声明"对外承诺的响应结构"**，返回对象会被过滤、校验、序列化——敏感字段天然不会泄露。

```python
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()
class UserIn(BaseModel):
    username: str
    password: str                       # 内部字段
class UserOut(BaseModel):
    username: str                       # 没有 password——响应模型把它过滤掉
users: dict[str, dict] = {"admin": {"username": "admin", "password": "x"}}
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserIn):
    users[body.username] = body.model_dump()
    return body                         # 含 password，但响应只输出 UserOut
```

要点：

- **`response_model` 是接口契约**：多余的键被丢弃、缺的键报错，配合 `status_code` 构成完整契约，OpenAPI 文档（3.10）也据此生成。
- **坑（密码泄露）**：不声明 `response_model`，`return users[username]` 会把 `password` 原样返回——**一切响应先定义输出模型**。
- 定制输出：`response_model_exclude/include`、`response_model_exclude_unset=True`；`204` 响应直接 `return None`。

### 3.6 认证鉴权（JWT 签发与校验·OAuth2 基础）

**JWT（JSON Web Token）** 是"签名自包含、服务端无状态"的令牌：签发后服务端不存会话，任何请求携带即可验证（原理见 4.5）。配合 **OAuth2PasswordBearer** 获得标准化的 token 提取方式。

```python
# 依赖：pip install pyjwt
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
SECRET_KEY = "dev-secret-change-me-in-production-32bytes"     # 生产必须环境变量注入
ALGORITHM = "HS256"
app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
def create_token(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id),
                       "exp": datetime.now(timezone.utc) + timedelta(hours=24)},
                      SECRET_KEY, algorithm=ALGORITHM)
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:              # 过期/篡改在此抛错
        raise HTTPException(status_code=401, detail="无效或过期的 token")
    return {"user_id": int(payload["sub"])}
```

要点：

- **鉴权 = 依赖注入**：`Depends(get_current_user)` 挂在受保护路由上，token 失败统一 401——每个路由零重复代码。
- **坑（密码明文存储）**：数据库只存**哈希**（`hashlib.pbkdf2_hmac`，生产用 bcrypt/argon2），绝不存明文；`exp` 必设；`SECRET_KEY` 走环境变量。
- OAuth2 基础：password 流程是"用户名密码 → access_token"的标准形态，`tokenUrl` 让 `/docs` 的 **Authorize 按钮**自动可用；JWT 无状态、无法主动吊销——短期 token + refresh token 是生产常见组合。

### 3.7 SQLAlchemy 与 Alembic（模型·会话·迁移）

SQLAlchemy 2.0 用 `Mapped` + `mapped_column` 类型化声明模型；**Session** 是"工作单元"（原理见 4.4）；**Alembic** 把表结构变更变成可版本化的迁移脚本。

```python
# 依赖：pip install sqlalchemy alembic
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
engine = create_engine("sqlite:///devices.db", connect_args={"check_same_thread": False})
class Base(DeclarativeBase):
    pass
class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[str] = mapped_column(unique=True, index=True)
    model: Mapped[str]
    online: Mapped[bool] = mapped_column(default=False)
Base.metadata.create_all(engine)          # 演示建表；正式项目用 Alembic
with Session(engine) as session:
    session.add(Device(vin="V001", model="EV-A"))
    session.commit()                      # 忘记 commit = 数据没写进去
```

```bash
alembic init alembic
alembic revision --autogenerate -m "create devices table"   # 需先改 env.py 指向 Base.metadata
alembic upgrade head
```

要点：

- **迁移脚本让结构变更可追踪**：`autogenerate` 对比"模型 vs 数据库"生成迁移，多环境执行同一份 `upgrade head`，杜绝手工 `ALTER TABLE` 对不上。
- **坑（SQLAlchemy 会话泄漏）**：Session 必须**用完关闭**（`with` 或依赖注入 `yield`），否则连接池被占满直至超时——用依赖注入管理会话生命周期（示例 4），每请求一个 Session。
- **坑（同步 Session 阻塞 async）**：默认 SQLAlchemy 是同步的，在 `async def` 路由里调用会**阻塞事件循环**——异步接口要配套异步依赖（roadmap 必会概念）：用 `async_sessionmaker` + `aiosqlite`，或该路由用普通 `def`（FastAPI 丢进线程池）。
- **坑（N+1 查询）**：ORM 懒加载在循环里逐条查库——列表接口用 `selectinload`/`joinedload` 预加载（ph11 深入）。

### 3.8 中间件与 CORS（middleware·跨域）

**中间件（middleware）** 包在所有路由外面：每个请求先进中间件、再进路由、响应原路返回——适合日志、耗时统计、请求 ID、CORS 等横切逻辑。

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:3000"],   # 前端域名白名单
                   allow_methods=["*"],
                   allow_headers=["*"])
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print("before:", request.method, request.url.path)
    response = await call_next(request)     # 调用下一层（路由）
    print("after:", response.status_code)
    return response
```

要点：

- **CORS 是浏览器策略，不是服务器策略**：服务端只是返回 `Access-Control-Allow-*` 响应头；纯 API 客户端（curl/脚本）不受影响。
- **坑（CORS 配置）**：`allow_origins=["*"]` 与 `allow_credentials=True` 不能同时用（浏览器规范禁止）；白名单按**协议+域名+端口**精确写（`localhost:3000` ≠ `localhost:8080`）。
- 中间件必须是异步的：`async def` + `await call_next(request)`。

### 3.9 日志与统一错误处理（logging·HTTPException·自定义异常）

**错误处理要"统一"**：所有错误都变成结构化 JSON（`{"detail": ...}`），而不是一半 500 一半裸文本；**日志用 `logging` 取代 `print`**（承接 ph06 日志纪律）。

```python
import logging
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")
app = FastAPI()
class BizError(Exception):                  # 自定义业务异常
    def __init__(self, code: int, message: str):
        self.code, self.message = code, message
@app.exception_handler(BizError)            # 全局处理器：统一 JSON
async def biz_handler(request, exc: BizError):
    return JSONResponse(status_code=exc.code,
                        content={"detail": exc.message, "code": exc.code})
@app.exception_handler(RequestValidationError)   # 覆盖默认 422 结构
async def validation_handler(request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"detail": "参数校验失败", "errors": exc.errors()})
@app.get("/devices/{device_id}")
def get_device(device_id: int):
    if device_id <= 0:
        raise BizError(400, "device_id 必须为正整数")
    if device_id > 100:
        raise HTTPException(status_code=404, detail="设备不存在")
    logger.info("query device %s", device_id)
    return {"id": device_id}
```

要点：

- 三层错误处理：**内置 `HTTPException`**（最常用）、**自定义异常 + `exception_handler`**（业务错误统一形态）、**`RequestValidationError` 处理器**（让 422 带业务字段）。完整版见示例 5。
- **坑（裸 500）**：未捕获异常默认返回无信息的 500——用 `@app.exception_handler(Exception)` 兜底 `logger.exception()` 后返回统一 500，别把堆栈回给前端。
- 日志三要素：**请求方法 + 路径 + 状态码 + 耗时**（配合中间件）；生产再挂 `request_id` 串联一次请求的全部日志。

### 3.10 OpenAPI 文档（自动生成·Swagger UI）

FastAPI 从**类型注解与模型定义**自动生成 OpenAPI 3 规范：交互式 `/docs`（Swagger UI）、`/redoc`、机器可读的 `/openapi.json`。**OpenAPI 文档是交付物**（roadmap 必会概念）——它既是前端对接契约，也是联调、测试（ph13）与客户端代码生成的输入。

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
app = FastAPI(title="设备管理 API",
              description="车联网设备管理服务：设备 CRUD 与状态查询",
              version="1.0.0")
class Device(BaseModel):
    vin: str = Field(description="车辆识别码", min_length=17, max_length=17)
    model: str = Field(description="车型")
@app.get("/devices", tags=["设备"], summary="设备列表")
def list_devices(limit: int = 10):
    """按 limit 返回设备列表"""              # docstring 也会进文档
    return [{"vin": "V" + str(i), "model": "EV-A"} for i in range(limit)]
```

要点：

- **文档质量 = 代码质量**：`tags`/`summary`/`description`/`Field(description=...)`/docstring 都渲染进文档——"文档是交付物"意味着要当产品文档写。启动 `uvicorn main:app --reload --port 8000` 后，`/docs`（Swagger UI，可直接调试）、`/redoc`（阅读型）、`/openapi.json`（机器规范）三处自动可用。
- `response_model` 决定文档里的响应 schema：**没有它，文档只有 200 且无结构**（呼应 3.5）。
- **坑（文档与实现脱节）**：文档由代码生成，**改接口先改类型注解**——`/openapi.json` 是唯一真源，前端可据此生成 TS 类型。

## 4. 底层原理

### 4.1 ASGI 与 uvicorn 的事件循环

FastAPI 不是服务器，而是运行在 **ASGI** 之上的框架。ASGI 应用是接收 `(scope, receive, send)` 的异步可调用对象：`scope` 是请求描述，`receive`/`send` 是异步收/发通道。**uvicorn** 启动一个 **asyncio 事件循环**，用事件驱动并发处理连接——每个请求不是一条线程，而是一个协程任务；`await` 让出控制权，I/O 等待期间事件循环去跑别的任务。这就是"一个进程扛成千上万个慢请求"的原理，也是"同步阻塞代码放进 async 路由会卡死所有人"的原因：`requests.get` 是阻塞 I/O，`await` 不了，整个事件循环被它占住（呼应 3.7）。普通 `def` 路由由 FastAPI 自动丢进**线程池**执行，所以同步业务放 `def` 路由反而安全。

### 4.2 Pydantic v2 的 Rust 核心与校验流程

Pydantic v2 把核心重写为 **pydantic-core（Rust 实现）**：模型的校验逻辑被编译成一份 Rust 的**校验计划（validation schema）**，Python 侧只负责传值与拿结果。一次 `Vehicle(...)` 构造：输入 dict → 按字段逐个走 Rust 校验器（类型转换、`Field` 约束、`field_validator` 钩子）→ 失败收集结构化 `ValidationError` → 成功构建模型实例。相比 v1 的纯 Python 逐字段校验，转换与约束检查都在 Rust 层完成，**性能提升数倍到数十倍**——这正是"类型注解驱动校验"能用于高 QPS 接口的底气；`model_dump(mode="json")` 的序列化同样走 Rust 核心。

### 4.3 依赖注入的解析机制（缓存·作用域）

FastAPI 的 `Depends` 本质是**按需解析的依赖图**：启动时分析路由签名构建依赖树（依赖可以依赖别的依赖），每次请求按依赖图**深度优先解析**，结果缓存进该请求的依赖缓存——**同一请求内同名依赖只解析一次**（重复 `Depends(get_current_user)` 不会重复解码 token）。作用域上，FastAPI 依赖默认是**请求级（request scope）**：每个请求新建、请求结束销毁，天然适合"每请求一个数据库 Session"（见 4.4）；需要跨请求复用的对象（连接池、缓存客户端）显式创建为模块级单例或 `lru_cache` 依赖。这就是"异步接口要配套异步依赖"的机制来源：依赖本身也可能是 `async def`，同步依赖在 async 路由里同样会阻塞事件循环。

### 4.4 SQLAlchemy 的 Session 与 identity map

SQLAlchemy 的 **Session** 是"工作单元（Unit of Work）"：记录一次业务操作里所有对象的状态变化，在 `commit()` 时统一生成 SQL 写库。Session 内部有 **identity map（身份映射）**：以"表名 + 主键"为键缓存已加载的对象——同一主键在同一个 Session 内只有一个 Python 实例，第二次查询直接命中缓存，保证对象一致性并减少重复查询；代价是 Session **线程不安全**、生命周期必须短（一个请求一个 Session），否则缓存膨胀、连接占用。**"会话泄漏"的本质**：Session 没关，其底层连接不归还连接池，池耗尽后新请求全部阻塞——所以用依赖注入 `yield` 会话并在 `finally` 关闭（示例 4），正是让"每请求一个 Session"生命周期自动化的工程手段。

### 4.5 JWT 的无状态认证结构

JWT 是"**自包含、可验证、无状态**"的三段式令牌 `header.payload.signature`：`header` 声明算法（HS256）；`payload` 是声明（claims），标准字段 `sub`（主体）、`exp`（过期时间）、`iat`（签发时间）；`signature` 是签名——HMAC-SHA256 用密钥对 `header.payload` 计算得出。校验时服务端**只做计算不做存储**：重新计算签名比对，一致且未过期即可信。这就是"无状态"：**不需要查库确认会话**，多台服务器只要共享密钥就能验证同一令牌。代价：签发后**无法主动吊销**（只能靠短 `exp` + 黑名单/refresh token 缓解）；且 `payload` 只是 base64 编码**并非加密**——**敏感数据（密码）绝不能放进 payload**，签名只保证"没被篡改"，不保证"别人看不到"。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| Todo 待办 API（前后端分离） | FastAPI 路由 + Pydantic 校验 + CRUD + 404 处理 |
| 登录注册 | JWT 签发/校验 + 密码哈希 + OAuth2PasswordBearer + 依赖注入鉴权 |
| 文件上传（图片/OTA 包） | `UploadFile` + 扩展名/大小校验 + 落盘保存 |
| 设备管理 API | SQLAlchemy 模型 + Session + CRUD + Alembic 迁移 |
| 车辆遥测数据上报 | 请求体校验（速度/SOC 范围）+ 批量写入 + 按设备查询 |
| 内部工具 API / 自动化平台 | 轻量接口 + OpenAPI 文档 + 统一错误处理 + 日志 |
| 车联网数据平台后端 | REST 契约 + JWT 鉴权 + 中间件（日志/CORS）+ 数据库持久化 |

**不适合此阶段的事项**：

- 数据库与缓存深入（SQL 优化、事务隔离、索引、Redis 缓存、连接池）：ph11 数据库与缓存阶段
- 大规模异步与消息（Kafka、MQ、百万级并发连接）：ph14 并发阶段（本阶段 async 只做入门）
- 生产部署（Nginx、Docker、K8s、CI/CD、日志收集、监控告警）：ph16 部署阶段
- 前端页面渲染（模板引擎、Django Admin、SPA 集成）：本阶段只交付 JSON API

## 6. 代码示例

### 示例 1：Todo API（FastAPI + Pydantic + 内存存储）

呼应"Todo API"练习：完整增删改查 + 参数校验 + 404 处理，内存存储起步，数据库版见示例 4。

```python
# 依赖：pip install "fastapi[standard]"；启动：uvicorn main:app --reload
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
app = FastAPI(title="Todo API")
class Todo(BaseModel):
    title: str = Field(min_length=1, max_length=100)   # 校验：非空、限长
    done: bool = False
todos: dict[int, Todo] = {}          # 内存存储（重启丢失；生产用数据库）
@app.post("/todos", status_code=201)
def create_todo(todo: Todo):
    todo_id = max(todos, default=0) + 1
    todos[todo_id] = todo
    return {"id": todo_id, **todo.model_dump()}
@app.get("/todos")
def list_todos(done: bool | None = None):      # 可选查询参数过滤
    result = [{"id": i, **t.model_dump()} for i, t in todos.items()]
    if done is not None:
        result = [t for t in result if t["done"] == done]
    return result
@app.get("/todos/{todo_id}")
def get_todo(todo_id: int):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    return {"id": todo_id, **todos[todo_id].model_dump()}
@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: Todo):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    todos[todo_id] = todo
    return {"id": todo_id, **todo.model_dump()}
@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    todos.pop(todo_id, None)
```

要点：`status_code=201/204` 语义化；`Field(min_length=...)` 一行完成校验；`{"id": i, **model_dump()}` 是"模型 + 附加字段"组合响应的常见写法。启动后打开 `/docs` 直接调试，title 传空串应返回 422；把 `todos` 换成 SQLAlchemy Session 即数据库版。

### 示例 2：登录注册（JWT 签发 + 依赖注入鉴权）

呼应"登录注册"练习：注册只存**密码哈希**，登录签发 JWT，受保护接口用 `Depends(get_current_user)` 鉴权。

```python
# 依赖：pip install "fastapi[standard]" pyjwt；启动：uvicorn main:app --reload
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
SECRET_KEY = "dev-secret-change-me-in-production-32bytes"       # 生产必须从环境变量读取
ALGORITHM = "HS256"
app = FastAPI(title="Auth API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
users: dict[str, str] = {}                # username -> 密码哈希（演示用内存）
class AuthBody(BaseModel):
    username: str
    password: str
def hash_password(password: str) -> str:                 # 绝不存明文
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 salt.encode(), 100_000).hex()
    return f"{salt}${digest}"
def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    return hashlib.pbkdf2_hmac("sha256", password.encode(),
                               salt.encode(), 100_000).hex() == digest
def create_token(username: str) -> str:
    return jwt.encode({"sub": username,
                       "exp": datetime.now(timezone.utc) + timedelta(hours=24)},
                      SECRET_KEY, algorithm=ALGORITHM)
@app.post("/auth/register", status_code=201)
def register(body: AuthBody):
    if body.username in users:
        raise HTTPException(status_code=409, detail="用户名已存在")
    users[body.username] = hash_password(body.password)
    return {"username": body.username}
@app.post("/auth/login")
def login(body: AuthBody):
    stored = users.get(body.username)
    if not stored or not verify_password(body.password, stored):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"access_token": create_token(body.username), "token_type": "bearer"}
def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except jwt.PyJWTError:                               # 过期/被篡改都在这
        raise HTTPException(status_code=401, detail="无效或过期的 token")
@app.get("/auth/me")
def me(username: str = Depends(get_current_user)):       # 受保护接口
    return {"username": username}
```

要点：密码用 **PBKDF2 加盐哈希**（生产换 bcrypt/argon2）；token 带 `exp` 且统一捕获 `PyJWTError`；鉴权收敛进 `get_current_user` 依赖，新接口只加一个 `Depends` 参数（呼应"API 层不应写复杂业务"）。调试：`/docs` 里注册 → 登录拿 token → 右上角 Authorize 粘贴 → 调 `/auth/me`。

### 示例 3：文件上传（UploadFile + 保存 + 校验）

呼应"文件上传"练习：校验扩展名与大小，防路径穿越，随机文件名落盘。

```python
# 依赖：pip install "fastapi[standard]" python-multipart；启动：uvicorn main:app --reload
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, File, HTTPException, UploadFile
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".bin", ".txt"}
MAX_SIZE = 5 * 1024 * 1024            # 5MB
app = FastAPI(title="Upload API")
@app.post("/upload")
async def upload(file: UploadFile = File(...)):          # 文件参数必用 File(...)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")
    content = await file.read()                           # UploadFile 是异步接口
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 5MB")
    dest = UPLOAD_DIR / f"{uuid4().hex}{suffix}"          # 随机名，防覆盖/穿越
    dest.write_bytes(content)
    return {"filename": file.filename, "saved_as": dest.name,
            "size": len(content)}
```

要点：**`UploadFile` 必须 `await file.read()`**（普通 `def` 路由用 `file.file.read()` 同步读）；校验顺序：扩展名 → 大小 → 落盘；**文件名永远服务端生成**（`uuid4`），用户文件名只作展示，杜绝路径穿越与同名覆盖；大文件应分块写盘（循环 `await file.read(1MB)`），一口气读会吃满内存。用 `curl -F "file=@test.txt" http://127.0.0.1:8000/upload` 验证，传 `.exe` 应返回 400。

### 示例 4：设备管理 API（SQLAlchemy + Alembic 迁移 + CRUD）

呼应"设备管理 API"练习：数据库版 CRUD，**Session 由依赖注入管理**（防会话泄漏），`response_model` 输出契约。

```python
# 依赖：pip install fastapi uvicorn sqlalchemy alembic；启动：uvicorn main:app --reload
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
DATABASE_URL = "sqlite:///devices.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
class Base(DeclarativeBase):
    pass
class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[str] = mapped_column(unique=True, index=True)
    model: Mapped[str]
    online: Mapped[bool] = mapped_column(default=False)
Base.metadata.create_all(engine)          # 首次运行建表；正式项目用 Alembic 迁移
class DeviceIn(BaseModel):                  # 输入模型
    vin: str = Field(min_length=17, max_length=17)
    model: str
class DeviceOut(DeviceIn):                  # 输出契约：无内部字段
    id: int
    online: bool
    model_config = {"from_attributes": True}   # 允许从 ORM 对象序列化
app = FastAPI(title="设备管理 API")
def get_session():                          # 依赖注入：每请求一个 Session
    with Session(engine) as session:        # 用完自动 close，防连接泄漏
        yield session
@app.post("/devices", status_code=201, response_model=DeviceOut)
def create_device(body: DeviceIn, session: Session = Depends(get_session)):
    device = Device(vin=body.vin, model=body.model)
    session.add(device)
    try:
        session.commit()
    except IntegrityError:                  # 唯一约束冲突（vin 重复）
        raise HTTPException(status_code=409, detail="vin 已存在")
    session.refresh(device)
    return device
@app.get("/devices", response_model=list[DeviceOut])
def list_devices(session: Session = Depends(get_session)):
    return session.scalars(select(Device)).all()
@app.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device
@app.put("/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, body: DeviceIn,
                  session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    device.vin, device.model = body.vin, body.model
    session.commit()
    return device
@app.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    session.delete(device)
    session.commit()
```

要点：依赖注入 `yield` 会话 = "每请求一个 Session、用完必关"（对应 4.4 的连接池原理）；`response_model=DeviceOut` + `from_attributes` 让 ORM 对象直接序列化且**不带内部字段**；`IntegrityError` 显式转 409。首次运行前配好 alembic 后执行 `alembic revision --autogenerate -m "create devices table"` 与 `alembic upgrade head`；改模型后重跑 autogenerate 追踪结构变更。

### 示例 5：统一错误处理与中间件（HTTPException + 日志中间件 + CORS）

综合"Middleware、日志、错误处理"：一个可复用的服务骨架，覆盖 CORS、请求日志中间件、业务异常与校验异常的统一 JSON 化。

```python
# 依赖：pip install "fastapi[standard]"；启动：uvicorn main:app --reload
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")
app = FastAPI(title="Service Skeleton")
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:3000"],   # 前端白名单
                   allow_methods=["*"],
                   allow_headers=["*"])
@app.middleware("http")                     # 请求日志中间件
async def log_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    logger.info("%s %s -> %s (%.1f ms)", request.method,
                request.url.path, response.status_code,
                (time.perf_counter() - start) * 1000)
    return response
class BizError(Exception):                  # 业务错误：code + message
    def __init__(self, code: int, message: str):
        self.code, self.message = code, message
@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(status_code=exc.code,
                        content={"detail": exc.message, "code": exc.code})
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"detail": "参数校验失败", "errors": exc.errors()})
@app.exception_handler(Exception)           # 兜底：500 也统一 JSON + 记堆栈
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
@app.get("/devices/{device_id}")
def get_device(device_id: int):
    if device_id <= 0:
        raise BizError(400, "device_id 必须为正整数")
    if device_id > 100:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"id": device_id, "status": "online"}
```

要点：**所有错误路径返回同构 JSON**（`{"detail": ...}`），前端一个解析函数通吃；中间件统一记录"方法 + 路径 + 状态码 + 耗时"；`logger.exception` 只在兜底处理器里用（自动带堆栈）。验证：`/devices/0` 返回 400、`/devices/50` 返回 200 且终端打印请求日志。这个骨架可直接作为"设备数据上报 API"推荐项目的基础。

## 7. 总结

### 关键要点

1. **Pydantic 负责数据校验和序列化**：一个 `BaseModel` 同时承担校验、转换、序列化、OpenAPI schema 四份工作，非法输入自动 422（roadmap 必会概念）
2. **API 层不应写复杂业务**：路由只做"取参数 → 调业务 → 返回响应"，业务逻辑收敛到 service 层/依赖里（roadmap 必会概念）
3. **异步接口要配套异步依赖**：`async def` 路由只 `await` 异步操作（含异步 Session/UploadFile），同步阻塞放 `def` 路由进线程池（roadmap 必会概念）
4. **OpenAPI 文档是交付物**：`/docs` 即契约——`tags`/`summary`/`Field(description)`/`response_model` 当产品文档写（roadmap 必会概念）
5. **`response_model` 是响应契约**：输出模型过滤敏感字段、定义结构——不声明它，`password` 可能原样返回
6. **密码绝不存明文**：PBKDF2/bcrypt 加盐哈希 + JWT 带 `exp` + 密钥走环境变量；JWT 无状态、不可主动吊销
7. **Session 生命周期必须短**：每请求一个 Session、依赖注入 `yield` 用完即关，防连接池泄漏；`commit()` 忘写 = 数据丢失
8. **Alembic 让结构变更可追踪**：`autogenerate` 对比模型生成迁移，多环境执行同一份 `upgrade head`
9. **错误处理要统一**：`HTTPException`/自定义异常/`RequestValidationError`/兜底 500 全部输出同构 JSON；日志记"方法 + 路径 + 状态码 + 耗时"
10. **中间件管横切**：日志、CORS、耗时统计放中间件；CORS 白名单精确到"协议+域名+端口"，`*` 与 `credentials` 不可同用

### 跨语言对比：Web 框架

| 维度 | Python（FastAPI） | Go（Gin） | Java（Spring Boot） | Node（Express） | Rust（Axum） |
|------|-------------------|-----------|---------------------|-----------------|--------------|
| 定位与风格 | 类型驱动、自动文档 | 极简路由 + 中间件链 | 全家桶、约定优于配置 | 极简中间件、生态大 | 类型安全、tokio 异步 |
| 路由与参数 | 装饰器 + 类型注解 | `gin.Engine` 注册 | `@GetMapping` 注解 | `app.get(...)` | `Router` + handler |
| 参数校验 | Pydantic（自动 422） | binding tag | Bean Validation | 手动/joi/zod | serde + validator |
| 依赖注入 | `Depends`（内置，请求级） | 手动 / uber-dig | Spring 容器（IoC） | 手动 | 手动 / extensions |
| 数据库 ORM | SQLAlchemy | GORM | JPA / Hibernate | Sequelize / Prisma | sqlx / Diesel |
| API 文档 | OpenAPI 自动生成 | swaggo | springdoc | swagger-ui 手动接入 | utoipa |

### 阶段验收标准

- 能启动 FastAPI 服务：`uvicorn main:app --reload` 后 `/docs` 可访问、接口可调（对应 roadmap"能启动 FastAPI 服务"）
- 能做参数校验：Pydantic 模型 + 路径/查询/请求体参数，非法输入返回结构化 422（对应 roadmap"能做参数校验"）
- 能连接数据库：SQLAlchemy 定义模型、CRUD 读写、Alembic 迁移建表（对应 roadmap"能连接数据库"）
- 能实现 JWT 登录注册与鉴权，受保护接口带 `Depends` 校验 token，并解释四个必会概念
- 能写中间件与统一错误处理：请求日志 + CORS + 全错误路径同构 JSON

### 进入下一阶段前

确保能完成以下练习：

- Todo API：内存存储起步，POST/GET/PUT/DELETE + 404 + `Field` 校验（提示：先 `/docs` 调通；`status_code=201/204` 语义化；title 空串应 422）
- 登录注册：密码哈希 + JWT 签发 + `Depends(get_current_user)` 保护接口（提示：`/docs` 的 Authorize 按钮贴 token 调试；`exp` 一定设置；验证 401 分支）
- 文件上传：`UploadFile` + 扩展名/大小校验 + 随机文件名落盘（提示：`await file.read()`；`python-multipart` 必须装；传 `.exe` 应 400）
- 设备管理 API：SQLAlchemy 模型 + Alembic 迁移 + CRUD + `response_model`（提示：依赖注入 `yield` 会话防泄漏；重复 vin 捕获 `IntegrityError` 返回 409；改模型后跑 `alembic revision --autogenerate`）
- 综合骨架：把示例 5 的中间件 + 统一错误处理套到 Todo API 上（提示：验证 400/404/422 三种错误响应结构一致；观察终端请求日志）

### 推荐项目

- **OTA 管理 API**：设备 + 固件版本 + 升级任务三张表（SQLAlchemy + Alembic），OTA 固件包走示例 3 的文件上传（校验扩展名与大小），升级任务与设备接口 JWT 鉴权，统一错误处理骨架（呼应 roadmap"OTA 管理 API"；三个练习能力的合体）
- **设备数据上报 API**：车辆遥测上报接口 `POST /telemetry`（请求体校验：速度 0~200、SOC 0~100），按设备/时间查询与统计（结合 ph09 分组统计思维），批量写库，日志中间件记录每条上报的耗时与状态码（呼应 roadmap"设备数据上报 API"；车联网数据平台方向的基础服务）

### 下一阶段

[数据库与缓存阶段](../ph11-database/11-database.md) —— SQL 深入、PostgreSQL/MySQL、Redis 缓存、事务与迁移。
