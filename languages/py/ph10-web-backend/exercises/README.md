# exercises —— Web 后端阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节一一对应：Todo API、登录注册、文件上传、设备管理 API。

完成顺序建议：按 1~4 顺序完成（逐步叠加：路由/Pydantic → JWT 鉴权 → 文件 → 数据库）。

## 依赖与验证方式

- 依赖安装：`pip install fastapi uvicorn httpx sqlalchemy pyjwt python-multipart pytest`（承接 ph07 的 venv 做法，先在虚拟环境里装；fastapi 的 `TestClient` 需要 httpx）
- 本阶段练习**优先用 `TestClient` 离线验证**（不占端口、不留进程）：`client = TestClient(app)` 后像真客户端一样调接口、断言状态码与响应体；确需起真实服务看效果的，用 `uvicorn main:app --port 8765` 跑完立刻 Ctrl-C 或 `kill` 干净
- 产物纪律：sol 里所有数据库文件、上传文件、下载产物一律写到**系统临时目录**（`tempfile.mkdtemp`），运行后当前目录不得残留任何文件

## 练习 1：Todo API（★）

- **目标**：用 FastAPI + Pydantic 写一个内存版 Todo 增删改查 API
- **要求**：
  - `POST /todos`（201）创建；`GET /todos`（200）列表、支持 `?done=true|false` 过滤；`GET /todos/{id}`（200）；`PUT /todos/{id}`（200）整体更新；`DELETE /todos/{id}`（204）
  - `Todo` 模型：`title` 用 `Field(min_length=1, max_length=100)` 约束，`done` 默认 `False`；不存在返回 404（`{"detail": ...}`）
  - 用 `TestClient` 写完每步断言：创建 201 → 列表 200 → 空 title 422 → 不存在 404
- **验收**：五个方法全部可用且状态码与上述一致；title 空串返回 422；内存存储重启即丢（说明这一点即可，不用数据库）

## 练习 2：登录注册（★★）

- **目标**：实现注册（只存密码哈希）、登录签发 JWT、`Depends` 保护受保护接口
- **要求**：
  - `POST /auth/register`（201）：用户名重复返回 409；**密码绝不存明文**——用 `hashlib.pbkdf2_hmac("sha256", ...)` 加盐哈希后存储（盐随机、100_000 次迭代，格式自定如 `salt$digest`）
  - `POST /auth/login`（200）：验证哈希后签发 JWT（`pyjwt`，HS256，`sub` 放用户名、**必须带 `exp`**）；用户名或密码错误返回 401
  - `GET /auth/me`：`Depends(get_current_user)` 从 `Authorization: Bearer <token>` 解出用户名返回；无 token / 过期 / 被篡改统一 401
  - 用 `TestClient` 断言：注册 201 → 重复 409 → 登录 200 拿到 token → 带 token 调 `/auth/me` 200 → 不带 token 401 → 篡改过的 token 401 → 过期 token 401
- **验收**：内存注册表里存的是哈希不是明文（打印出来肉眼确认）；错误 token 三种情况（缺失/过期/篡改）都返回 401

## 练习 3：文件上传（★★）

- **目标**：用 `UploadFile` 实现带校验的文件上传并落盘
- **要求**：
  - `POST /upload`：`file: UploadFile = File(...)`；允许扩展名集合（如 `.txt/.png/.jpg/.jpeg/.bin`），不在集合内返回 400
  - 大小上限 5MB，超限返回 413；**用 `await file.read()` 读取**（`async def` 路由）
  - 落盘文件名**服务端生成**（`uuid4().hex + 后缀`），用户文件名只作展示——防路径穿越与同名覆盖；上传目录用临时目录
  - 用 `TestClient` 构造 `files={"file": ("a.txt", b"hello", "text/plain")}` 断言：合法 200、`.exe` 400、超 5MB 413、缺文件 422
- **验收**：三种失败分支（类型/大小/缺失）状态码与提示正确；落盘文件在临时目录、名字是随机串；当前目录无残留

## 练习 4：设备管理 API（★★★）

- **目标**：SQLAlchemy 2.0（`Mapped` 风格）+ SQLite + `response_model` 的数据库版 CRUD
- **要求**：
  - `Device` 模型：`id` 主键、`vin` 唯一 + 索引、`model`、`online`（默认 False）；`create_engine("sqlite:///<临时目录>/devices.db")`
  - **Session 用依赖注入管理**：`def get_session()` 里 `with Session(engine) as session: yield session`——用完自动关闭，防连接泄漏（主文档 4.4）
  - 输入模型 `DeviceIn`（`vin` 限长 17、`model`），输出模型 `DeviceOut`（含 `id`/`online`，`model_config = {"from_attributes": True}`）；`POST` 201、`GET` 列表/单个、`PUT`、`DELETE` 204，不存在 404，重复 `vin` 捕获 `IntegrityError` 返回 409
  - 用 `TestClient` 断言全链路 + 重复 vin 409 + 不存在 404
- **验收**：CRUD 全通；重复 vin 409；数据库文件在临时目录（`sqlite:///...` 路径用 `Path(tempfile.mkdtemp(...))` 拼）；说清"依赖注入 `yield` Session"为什么能防连接池泄漏

> **提示**：练习 1~4 与主文档 3.x 小节一一对应（3.2/3.3/3.4/3.5 路由与模型、3.6 认证鉴权、3.9 错误处理、3.7 数据库）；做完后对照 `sol-*` 参考实现复盘——先独立完成，再看答案。
