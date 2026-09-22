# examples —— Web 后端阶段完整示例

> 每个示例对应主文档 `10-web-backend.md` 相关小节（3.x / 4.x / 6 章）的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：fastapi 0.139.1、starlette 0.49.3、pydantic 2.12.4、uvicorn 0.50.0、httpx 0.28.1、jinja2 3.1.6。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-wsgi-asgi.py` | WSGI/ASGI 协议应用：不建服务器，直接驱动应用可调用对象（主文档 4.1、3.1） | `python3 ex01-wsgi-asgi.py`（离线） |
| `ex02-http-server.py` | http.server 标准库基线：线程内起服务 → 请求 → 干净关闭（主文档 3.1） | `python3 ex02-http-server.py`（离线） |
| `ex03-routing-di-middleware.py` | FastAPI 路由 + 依赖注入链 + 中间件 + 依赖缓存（主文档 3.2/3.4/3.8/4.3） | `python3 ex03-routing-di-middleware.py`（离线） |
| `ex04-jinja2-template.py` | Jinja2 模板渲染：变量插值 / if / for / 过滤器（主文档 3.11；模板在 `templates/device.html`） | `python3 ex04-jinja2-template.py`（离线） |
| `ex05-static-files.py` | 静态文件与 FileResponse：`/static/*` 资源服务 + 动态 CSV 下载（主文档 3.11；资源在 `static/style.css`） | `python3 ex05-static-files.py`（离线） |
| `ex06-async-concurrency.py` | 异步接口与并发：串行 vs 并发耗时对比（主文档 3.12/4.1） | `python3 ex06-async-concurrency.py`（离线） |

说明：

- **不起真实服务**：ex01/ex03~ex06 用「直驱应用对象 / `fastapi.testclient.TestClient` / `httpx.ASGITransport`」在进程内验证，不占端口、不留进程；ex02 是唯一真实起服务的示例——`ThreadingHTTPServer` 绑定端口 0（操作系统分配高位空闲端口），脚本内 `shutdown()` + `server_close()` 干净关闭。
- **产物纪律**：ex05 动态生成的 CSV 写到系统临时目录（`tempfile.mkdtemp`），不在仓库残留；运行后用 `git status` 可确认工作区干净。
- 模板与静态资源：`templates/device.html`、`static/style.css` 分别为 ex04/ex05 的资源目录（ex04 渲染的页面会引用 `/static/style.css`，配合 ex05 的挂载逻辑）。

验证状态：全部示例均已在本环境实际运行通过（已验证）。实测关键输出：

- `ex01`：WSGI 直驱 `200 OK` + JSON `{"path": "/api/status", "method": "GET"}`；ASGI 直驱 `200` + JSON `{"path": "/devices/V001/telemetry", "method": "GET"}`
- `ex02`：`GET / → 200 hello from stdlib http.server`；`GET /health → 200 {"status": "ok", "service": "http.server"}`；脚本结束打印「服务已关闭，端口已释放」
- `ex03`：`/items/me → 200 {"item": "ME"}`；`/items/42?q=abc → 200`（含 `X-Elapsed-Ms` 头）；`/items/not-a-number → 422`（`int_parsing`）；`/calls → {"c1": 3, "c2": 3}`——同一请求内同名依赖只解析一次
- `ex04`：`/device/V001 → 200 text/html`，渲染片段全部命中（标题/车型/在线/速度保留 1 位小数/共 3 条记录）；`/device/V002 → 200` 离线与空列表分支生效；`/device/UNKNOWN → 404`
- `ex05`：`/static/style.css → 200 text/css`（337 字节）；`/static/missing.css → 404`；`/download/report → 200 text/csv`，`Content-Disposition: attachment; filename="report.csv"`
- `ex06`：串行 3 个 0.3s 慢请求 ≈ 0.91s；并发 3 个 ≈ 0.30s（事件循环让出并发，见主文档 4.1）
