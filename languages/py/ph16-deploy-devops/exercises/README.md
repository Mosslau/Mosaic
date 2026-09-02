# exercises —— 部署与 DevOps 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap 第 16 节「练习」小节一一对应：部署 FastAPI 服务（练习 1）、Docker Compose 启动服务和数据库（练习 2）、Nginx 反向代理（练习 3）、配置 systemd（练习 4）。完成顺序建议按 1~4：先把服务做成「可部署形态」，再逐层套上编排、反代与进程守护。

## 依赖与验证方式

- 依赖：fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1（本机已装并实测）；练习 2 需要 Docker Compose CLI（语法检查不需要 daemon）；练习 3 需要 nginx（`nginx -t` 语法检查）；练习 4 需要 Linux + systemd（**本机 macOS 无 systemd，sol-04 未在本环境验证**）
- 运行：`python3 sol-01-deploy-fastapi.py`（进程内 TestClient 自检，断言失败会报错退出）；`docker compose -f sol-02-docker-compose.yml config`（离线语法解析）；`nginx -t -c sol-03-nginx.conf`（语法检查，需 mime.types 在 conf 同目录）
- 参考实现文件头带**验证块**（环境、验证命令、验证状态），先独立完成再看；本机 daemon 未启动，compose 类文件只有语法级验证，你的机器上 daemon 可用时应实际 `up` 一遍

## 练习 1：部署 FastAPI 服务（★）

- **目标**：把一个 FastAPI 应用改造成「可部署形态」（对应 roadmap「部署 FastAPI 服务」）
- **要求**：
  - 提供 `/health`（liveness：进程活着即 200）与 `/ready`（readiness：模型/依赖就绪才 200，否则 503）两个探针，且能说明二者分工
  - 用 lifespan 钩子在启动时加载「模型」（可用 `time.sleep`/标志位模拟），加载失败 readiness 必须变 503
  - 输入用 Pydantic 模型校验（非法输入 422）；给出生产启动命令（uvicorn，`--host 0.0.0.0`，不带 `--reload`）
- **验收**：TestClient 或真实 uvicorn + httpx 断言：/health 200、/ready 200、依赖故障时 /ready 变 503 而 /health 仍 200、非法输入 422；**把实测输出写进验证块**

## 练习 2：Docker Compose 启动服务和数据库（★★）

- **目标**：用一个 compose 文件同时拉起 Web 服务与 PostgreSQL（对应 roadmap「Docker Compose 启动服务和数据库」）
- **要求**：
  - `web` + `db` 两个服务；web 通过环境变量拿数据库连接串（配置与代码分离）
  - `depends_on` 必须用 `condition: service_healthy`（db 配 `pg_isready` 健康检查），不能只等容器启动
  - 数据库用命名卷持久化；db 不暴露端口到宿主机；两个服务都配 `restart`
- **验收**：`docker compose config` 解析通过；daemon 可用时 `up -d` 后 web 健康检查 200、`psql` 能连上库；**如实标注验证级别**（语法级 / 实际启动）

## 练习 3：Nginx 反向代理（★★）

- **目标**：给 uvicorn 服务套一层 Nginx 反代（对应 roadmap「Nginx 反向代理」）
- **要求**：
  - `upstream` 声明至少 2 个后端实例，`location /` 反代并透传 `Host` / `X-Real-IP` / `X-Forwarded-For` / `X-Forwarded-Proto`
  - `/health` 单独直通（探针流量不受限流影响）；给 API 路径加 `limit_req` 限流
  - 加分项：WebSocket 路径的 `Upgrade`/`Connection` 头透传
- **验收**：`nginx -t -c <你的配置>` 语法检查通过；**把检查输出写进验证块**；daemon/端口可用时实际起反代链路打一遍

## 练习 4：配置 systemd（★★）

- **目标**：用 systemd 把 uvicorn 服务变成「开机自启、崩溃自拉起、日志可查」的系统服务（对应 roadmap「配置 systemd」）
- **要求**：
  - unit 三段齐全：`[Unit]`（After=network-online.target）、`[Service]`（ExecStart 生产形态、Restart、低权限 User、EnvironmentFile）、`[Install]`（WantedBy=multi-user.target）
  - 日志走 journald（StandardOutput=journal）；防「拉挂循环」的 StartLimit 配置
  - 加分项：`NoNewPrivileges`/`ProtectSystem` 等安全加固
- **验收**：能说清每个指令的作用；Linux 机器上 `systemd-analyze verify` / 实际 enable 启动验证；**macOS 上如实标注「未在本环境验证」**

> **提示**：练习 1~4 与主文档 3.x 小节一一对应（3.1 部署基础、3.3 Compose、3.4 Nginx/Gunicorn/Uvicorn、3.5 Supervisor/systemd）；ex01/ex03/ex04/ex05 的 examples 是它们的「已验证最小版」，卡住时先跑 examples 再做题。做完后对照 sol-* 参考实现复盘——先独立完成，再看答案。
