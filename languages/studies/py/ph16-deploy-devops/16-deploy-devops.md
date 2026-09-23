# Python 部署与 DevOps 阶段

> 面向「让服务在真实环境长期、可观测地活着」，本阶段把 ph10 写的 FastAPI 应用、ph15 训出的 joblib 模型产物，一路送进「镜像 → 编排 → 反代 → 进程守护 → CI/CD → 监控」的完整链路——四个必会概念（部署环境要可复现、配置与代码分离、服务要有健康检查、日志和监控是排障基础）每一条都落成可验证的配置或实测。

## 1. 概述

Python 部署与 DevOps 阶段的目标是：**把 Python 项目部署到真实环境**（roadmap 第 16 节目标）。它是学习路线从「写对代码」转向「养好服务」的一站：承接 ph10 Web 后端开发阶段（FastAPI 应用怎么写，这里不重讲）与 ph15 AI / 机器学习阶段（joblib 模型产物 + cli.py 命令行推理——本阶段的 project/ 把它升级为带健康检查与指标端点的部署模板；`JoblibPredictor` 对 ph15 落盘的 `ComponentHealthPipeline` 产物形态做分派兼容，**但该兼容只到「形态」一级（stub 级验证，test_api.py 的 `Ph15LikePipeline`），真实 ph15 joblib 产物要在服务端加载，还需其 `health` 包可被 import——project 镜像不含 health，边界与解法见 project/README 扩展方向**），补上「代码写完到用户能用」之间的工程链路。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 部署基础 | Linux 进程/端口/环境变量、配置与代码分离（12-factor）、可复现环境（锁版本）——3.1 |
| 容器化 | Docker 镜像与 Dockerfile、多阶段构建、.dockerignore、Docker Compose 多服务编排——3.2/3.3 |
| 服务栈 | Nginx 反向代理 / Gunicorn 进程管理 / Uvicorn ASGI 服务器的分工与选型——3.4 |
| 进程守护 | Supervisor 与 systemd（开机自启、崩溃拉起、journald 日志）——3.5 |
| CI/CD | 流水线阶段（lint → test → build → deploy）、GitHub Actions 示例、部署策略概念——3.6 |
| 可观测性 | 日志采集（stdout → journald/容器）、Prometheus 四种指标、/metrics 端点、Grafana 看板、liveness vs readiness——3.7 |
| 底层原理 | WSGI vs ASGI 协议、多进程 worker 模型（pre-fork + GIL）、容器镜像分层与构建缓存——第 4 章 |
| 代码层 | 6 个示例（examples/）+ 4 个练习（exercises/）+ 综合项目（project/：部件健康预测服务部署模板） |

这个阶段只涉及**把 Python 服务部署起来并看护好的工程链路**——Linux 部署基础、Docker/Docker Compose、Nginx/Gunicorn/Uvicorn 服务栈、Supervisor/systemd 进程守护、CI/CD 流水线、日志采集与 Prometheus/Grafana 监控，**不涉及 Web 框架与接口设计本身（FastAPI 路由/Pydantic/中间件——那是 ph10 Web 后端开发阶段的内容，本阶段直接消费它的应用）、数据库与缓存的使用细节（ph11 数据库阶段，本阶段的 compose 只把 PostgreSQL 当「一个需要健康检查的依赖服务」演示）、并发与异步机制本身（asyncio/事件循环——ph14 并发、并行与异步阶段）和 Kubernetes 编排实战（K8s 是独立专题，本阶段只讲「为什么单机编排不够用」的概念地图，roadmap 第 16 节之外）**。本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

「部署」的形态演进，是一条**不断把「环境差异」关进笼子里**的历史：

- **物理机时代**：应用直接装在服务器操作系统上，「在我机器上是好的」是经典事故——环境 = 这台机器的历史操作总和，不可复现；
- **虚拟机时代**（VMware 1999 年起）：把整台机器（含操作系统）打包成镜像，环境可复现了，但每个应用背一个完整 OS，重（GB 级镜像、分钟级启动）；
- **容器时代**（Docker 2013）：利用 Linux 内核的 namespace（隔离）+ cgroup（限额），进程级隔离、共享宿主机内核——镜像只装「应用 + 依赖」（MB~百 MB 级），秒级启动。「构建一次，到处运行」终于成立；
- **编排时代**（Kubernetes 2014 起）：一台机器不够了——几百个容器在几十台机器上怎么调度、怎么自愈、怎么滚动更新？Google 把内部 Borg 的经验开源成 Kubernetes，2017 年前后击败 Docker Swarm/Mesos 成为事实标准。

配套的服务栈也在演进：Nginx（2004，Igor Sysoev 为解决 C10K 问题写的异步事件驱动服务器）取代 Apache 成为反代/静态服务主流；Python 侧从 WSGI（PEP 333，2003）演进到 ASGI（2015 起，为 async/WebSocket 而生），服务器从 Gunicorn/uWSGI 到 Uvicorn；进程守护从 Supervisor（2004）到 systemd（2010，现代 Linux 发行版标配）；监控从 Nagios「只报警」到 Prometheus（2012，SoundCloud）+ Grafana（2014）的「指标 + 看板」体系。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| VMware Workstation / ESX | 1999-2001 | x86 虚拟化商用，「整机打包」的部署形态 |
| AWS EC2 | 2006 | 虚拟机变成按秒租用的云服务，IaaS 时代 |
| Heroku / 12-Factor | 2007 / 2011 | PaaS 与「配置进环境变量」等部署方法论 |
| Docker 开源 / 1.0 | 2013 / 2014 | 容器 = 镜像 + namespace + cgroup，部署形态革命 |
| Kubernetes 开源 / 1.0 | 2014 / 2015 | Google 开源（源自 Borg），容器编排；2017 年前后成事实标准 |
| OCI 标准 | 2015 | 镜像与运行时标准化，containerd 等实现出现 |
| Supervisor / systemd | 2004 / 2010 | 进程守护：Supervisor 跨平台用户态；systemd 成 Linux 标配 |
| Gunicorn / Uvicorn | 2010 / 2017 前后 | WSGI pre-fork 服务器 / ASGI 事件循环服务器（uvicorn 仓库 2017 年建、2018 年 4 月首个 PyPI 发布，表中取约数） |
| Prometheus / Grafana | 2012 / 2014 | 拉模型指标监控 + 看板，云原生可观测性标配 |
| GitHub Actions | 2019 | CI/CD 与代码仓库合体，流水线即配置 |

本文示例以 **Python 3.13** 为基线（当前 CPython 稳定大版本，部署主流目标），验证工具链 **Python 3.13.9**（macOS arm64）；服务栈基线 **FastAPI 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1**（本机已装，服务类示例全部实测起真实服务）。环境限制如实声明：本机 Docker CLI 29.6.2 在但 **daemon 未启动**——Dockerfile/Compose 的构建与运行**未在本环境验证**（compose 文件做了 `docker compose config` 离线语法验证）；Homebrew **nginx 1.31.2** 在，反代配置做了 `nginx -t` 语法级验证但未起真实链路；**macOS 无 systemd**，unit 文件未在本环境验证（按 systemd 手册编写）。部署工具的语法（Dockerfile 指令、compose 结构、systemd 指令、Nginx 配置块）是各自生态里最稳定的接口层——这套「镜像 + 编排 + 反代 + 守护 + 监控」的分层心智长期成立。

## 3. 语法与参数

### 3.1 Linux 部署基础：进程、端口与环境变量

**部署 = 让一个进程在服务器上长期存活并对外服务**。拆解下来是四件事：进程怎么起（前台/后台、谁拉起）、端口怎么绑（`--host 0.0.0.0` 才对外可见，`127.0.0.1` 只对本机）、配置怎么进（环境变量）、日志去哪（stdout）。roadmap 必会概念「配置与代码分离」来自 12-Factor 方法论：**代码入库，配置进环境变量**——同一份代码 + 不同环境变量 = 开发/测试/生产三套环境：

```python
# project/app/predictor.py —— 配置从环境变量读，不写死在代码里（已验证）
raw = os.environ.get("MODEL_PATH", "").strip()   # 未设置 → 规则兜底
```

**部署环境要可复现**（roadmap 必会概念）：依赖必须锁版本（`requirements.txt` 写 `fastapi==0.139.1` 而不是 `fastapi`），基础镜像写 `python:3.13-slim` 而不是 `python:latest`——`latest` 明天就变，「可复现」要求半年后构建出的环境和今天一样。

常用排查命令（部署后的日常）：

| 命令 | 用途 |
|------|------|
| `ps aux \| grep uvicorn` | 进程在不在 |
| `lsof -i :8000`（macOS）/ `ss -tlnp`（Linux） | 谁占了 8000 端口 |
| `curl -v http://127.0.0.1:8000/health` | 服务通不通（部署后第一件事） |
| `kill -TERM <pid>` vs `kill -KILL <pid>` | 优雅关停（给清理机会）vs 强杀（最后手段） |
| `journalctl -u <服务名> -f` | 跟日志（systemd 场景，见 3.5） |

**信号如何被守护层感知（SIGTERM → 优雅关停的闭环）**：ex01 实测 uvicorn 收到 `SIGTERM` 后先打印 `INFO: Shutting down` / `INFO: Finished server process` 完成优雅收尾（停接新连接、等在途请求结束、刷日志），进程随后以「被 SIGTERM 终止」的形态退出（returncode -15，shell 显示 143）——**优雅关停 ≠ 退出码 0，收尾的证据在日志里**。守护层对这次退出怎么解读，决定要不要拉起：

- **systemd（`Restart=on-failure`）**：管理员 `systemctl stop` 自己发出 SIGTERM，systemd 记为「主动停止」，不触发重启（ex05 unit 注释同此语义）；
- **compose（`restart: unless-stopped`）**：`docker stop` 同样是先 SIGTERM、宽限期后仍不退才 SIGKILL；restart 策略只对「非主动停止」的退出生效；
- **裸 shell**：`kill -TERM` 前台进程后 shell 报 143（128+15），脚本可用退出形态区分「被优雅关停」与「自己崩了」。

所以优雅关停是一条完整链路：应用收到 SIGTERM → 自己收尾 → 守护层据退出形态决定是否拉起。若应用无视 SIGTERM 硬扛，systemd/compose 会在超时后升级 SIGKILL（-9）——那时连收尾机会都没有。

> 阶段内容隔离：FastAPI 应用本身怎么写（路由、校验、中间件）属于 ph10 Web 后端开发阶段，这里只谈「应用怎么变成长期存活的服务」。

### 3.2 Docker：镜像、Dockerfile 与多阶段构建

Docker 把「应用 + 依赖 + 启动命令」打成**镜像**（只读模板），运行的镜像实例叫**容器**（进程级隔离，共享宿主机内核）。Dockerfile 是镜像的构建配方，核心指令：

| 指令 | 作用 | 教学点 |
|------|------|--------|
| `FROM python:3.13-slim` | 选基础镜像 | slim 变体砍掉编译链，镜像小一个量级 |
| `WORKDIR` / `COPY` | 设工作目录 / 拷文件进镜像 | 每条指令产生一层（4.3 的分层与缓存） |
| `RUN pip install --no-cache-dir ...` | 构建期执行命令 | `--no-cache-dir` 不把 pip 缓存留在镜像里 |
| `ENV` / `EXPOSE` | 环境变量 / 声明端口 | EXPOSE 是文档性质，真正映射在 `docker run -p` |
| `USER appuser` | 非 root 运行 | 容器逃逸时的第二道防线 |
| `CMD` vs `ENTRYPOINT` | 默认命令 / 固定入口 | CMD 可被 `docker run` 参数覆盖，ENTRYPOINT 不行 |

**多阶段构建**（examples/ex02）：构建需要编译链和 pip 缓存，运行只需要 venv 和代码——分成 builder / runtime 两个阶段，最终镜像只 `COPY --from=builder` 拿运行必需品。下面是关键片段（节选，中间省略了 WORKDIR/ENV/USER/CMD 等行，完整文件见 `examples/ex02-docker-multistage/Dockerfile`，§6 示例 2 有完整版）：

```dockerfile
# examples/ex02-docker-multistage/Dockerfile —— 关键片段（节选），未在本环境验证（daemon 未启动）
FROM python:3.13-slim AS builder
COPY requirements.txt .                            # 先拷依赖清单：这层缓存由 requirements 是否变化决定
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
FROM python:3.13-slim
COPY --from=builder /opt/venv /opt/venv   # 构建期产物不进最终镜像
```

常用命令：`docker build -t 名:标签 .` / `docker run --rm -p 8000:8000 名` / `docker ps` / `docker logs -f` / `docker exec -it`。本机 daemon 未启动，构建类命令**未在本环境验证**（ex02 文件头有完整验证命令）。

### 3.3 Docker Compose：单机的多服务编排

一个服务很少单独活着：Web 服务要数据库，数据库要先就绪。**Compose 用一个 YAML 描述「一组服务怎么一起活」**（examples/ex03，语法已验证）：

```yaml
# examples/ex03-docker-compose/docker-compose.yml —— 语法已验证（docker compose config 离线解析）
services:
  web:
    build: ../ex02-docker-multistage
    depends_on:
      db:
        condition: service_healthy   # 等 db 真正可连接，不是只等容器进程起来
    restart: unless-stopped          # 挂了自动拉起（单机场景的守护角色）
  db:
    image: postgres:17
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U demo -d demo"]
```

关键结构：**services**（每个服务：build/image、ports、environment、volumes、depends_on、healthcheck、restart）；**volumes**（命名卷持久化——容器删了数据还在）；compose 自动建内部网络，服务名即主机名（`DATABASE_URL` 里写 `@db:5432`）。常用命令：`docker compose up -d --build` / `ps` / `logs -f` / `down`；`docker compose config` 离线解析校验语法（不需要 daemon，本机实测通过）。

**教学重点**：`depends_on` 不加 `condition: service_healthy` 只保证「容器启动了」——PostgreSQL 进程起来到能接受连接有几秒窗口，web 抢跑就会连接失败崩溃，靠 restart 救回来是「碰巧能工作」而不是「设计上正确」。

### 3.4 Nginx / Gunicorn / Uvicorn：服务栈的分工

生产环境的 Python Web 服务是**三层分工**，不是 uvicorn 裸奔：

```text
客户端 ──▶ Nginx（门卫：TLS 终止、静态文件、限流、缓冲、负载均衡）
              │ proxy_pass
              ▼
         Gunicorn（工头：pre-fork 多进程管理、worker 挂了重启）  ← WSGI 应用在这一层
              │ 或 uvicorn --workers N（ASGI 应用的多进程形态）
              ▼
         Uvicorn worker（ASGI 服务器：事件循环跑 FastAPI 应用）
```

| 服务器 | 协议 | 并发模型 | 适用 |
|--------|------|---------|------|
| Gunicorn | WSGI | pre-fork 多进程（同步 worker） | Flask/Django 同步应用 |
| Gunicorn + UvicornWorker | ASGI | 多进程 × 事件循环 | FastAPI 生产经典组合 |
| Uvicorn 直跑 | ASGI | 单进程事件循环（`--workers` 可多进程） | 容器内常见（守护交给 compose/K8s） |
| Hypercorn / Daphne | ASGI | 事件循环 | 替代选择 |

**选型规则一句话**：FastAPI（ASGI）→ uvicorn 或 `gunicorn -k uvicorn.workers.UvicornWorker`；Flask/Django（WSGI）→ gunicorn。容器场景常见形态是「uvicorn 单进程 × 多个容器副本」，进程管理交给编排层；裸机场景用 Gunicorn 管多个 Uvicorn worker。Nginx 反代的核心配置（examples/ex04，`nginx -t` 语法已验证）：

```nginx
# examples/ex04-nginx/nginx.conf —— 语法已验证（本机 nginx -t 通过）
upstream health_api {
    server 127.0.0.1:8000 max_fails=2 fail_timeout=10s;  # 后端池：挂掉的自动摘除
    keepalive 32;                                        # 到后端的长连接池
}
location / {
    proxy_pass http://health_api;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  # 透传真实客户端 IP
}
```

为什么需要 Nginx 这层：uvicorn 直接对公网时，慢客户端攻击、TLS 握手开销、静态文件占用 Python worker 都是问题——Nginx 用事件驱动模型（C 写的）处理连接层的脏活，Python worker 只管业务。

### 3.5 Supervisor 与 systemd：进程守护

**进程挂了谁拉起？开机谁启动？日志去哪？** 这是进程守护工具回答的三个问题：

| 维度 | systemd | Supervisor |
|------|---------|-----------|
| 地位 | 现代 Linux 发行版标配（PID 1） | 跨平台用户态工具（pip 安装） |
| 配置 | unit 文件（INI） | supervisord.conf（INI） |
| 日志 | journald（`journalctl -u 服务名`） | 自管日志文件（stdout_logfile） |
| 适用 | Linux 服务器首选 | 老系统/无 root/非 Linux 的兜底 |

systemd unit 的三段结构（examples/ex05 与 exercises/sol-04，**macOS 无 systemd，未在本环境验证**）：

```ini
# examples/ex05-systemd-metrics/health-api.service —— 未在本环境验证（macOS 无 systemd）
[Unit]
After=network-online.target          # 网络就绪后再启动
[Service]
ExecStart=/opt/health-api/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure                   # 异常退出才拉起（正常停止不拉）
RestartSec=3
StandardOutput=journal               # 日志进 journald
[Install]
WantedBy=multi-user.target           # enable = 开机自启
```

要点：`Restart=on-failure` 与 `always` 的区别——管理员手动 `systemctl stop` 不该被拉起来；`EnvironmentFile` 把配置注入进程环境（3.1 的配置分离落到系统层）；`User=` 低权限运行。常用命令：`systemctl enable --now 服务名`（自启 + 立即启动）/ `status` / `restart` / `journalctl -u 服务名 -f`。

Supervisor 的等价配置（examples/ex05-supervisord/supervisord.conf，INI 风格，用户态守护——无 root 权限或非 systemd 系统上的选择；**本机未装 Supervisor，未在本环境验证**，按官方文档编写）：

```ini
; examples/ex05-supervisord/supervisord.conf —— 未在本环境验证（本机未装 Supervisor）
[program:health-api]
command=/opt/health-api/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/opt/health-api
user=health
autostart=true                 ; supervisord 启动时拉起（对应 systemd enable）
autorestart=unexpected         ; 异常退出才拉起（对应 Restart=on-failure）
startretries=3                 ; 连续拉起失败 3 次后标 FATAL（对应 StartLimitBurst 防爆拉）
stdout_logfile=/var/log/health-api.log   ; Supervisor 自管日志（不进 journald）
environment=MODEL_PATH="/models/model.joblib"
```

> **边界**：本阶段配套以 systemd 为准（ex05/exercises/sol-04 的 unit 文件是主交付物），Supervisor 仅作对比——两者心智同构（启动/看护/日志三件事 + 「异常退出才拉起」的语义），Supervisor 优势在跨平台、无 root；systemd 优势在 Linux 标配、日志走 journald。supervisorctl 命令表见 conf 文件头注释。

> ⚠️ 容器场景通常**不用** systemd/Supervisor 管应用——`restart: unless-stopped`（compose）或 K8s 的重启策略接管了这个角色。一条判断规则：**谁创建容器/进程，谁负责它的生命周期**——不要在容器里再套一层守护进程。

### 3.6 CI/CD：从 push 到上线的流水线

CI（持续集成）= 每次提交自动验证（lint + test）；CD（持续交付/部署）= 验证过后自动构建产物、部署上线。GitHub Actions 把它写成仓库里的 YAML——**字段即流水线语义**，逐段走读（完整文件 examples/ex06-ci-cd.yml，语法已验证；下面为关键段节选，编号 ①~⑥ 与文件注释对应）：

```yaml
on:
  push: { branches: [main] }    # ① 触发过滤：只 main 的 push 触发（发布链入口）
  pull_request:                 #    PR 也触发——先跑 lint/test 自检，不发布
concurrency:                    # ② 并发控制：同一分支同时只保留一条流水线
  group: ci-${{ github.ref }}
  cancel-in-progress: true      #    新提交顶掉排队中的旧任务，省 runner 配额
jobs:
  quality:                      # 质量门禁 job：lint + test
    strategy: { matrix: { python-version: ["3.12", "3.13"] } }
                                # ③ matrix：一组参数展开成多份并行 job
    steps:
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }}, cache: pip }
                                #    缓存 key：requirements 没变就复用 pip 缓存
      - run: ruff check . && ruff format --check .   # lint 门禁
      - run: python -m pytest                        # test 门禁
  image:
    needs: quality              # ④ 依赖门禁：quality 全绿 image job 才启动
    environment: production     # ⑤ 发布门禁：environment 可配人工审批/环境级 secrets
    steps:
      - run: docker build -t health-api:${{ github.sha }} .
      # ⑥ 推送/部署的凭据只经 ${{ secrets.XXX }} 引用——secrets 存在仓库
      #    Settings → Secrets，绝不写进 YAML/代码（配置分离在 CI 层的体现）
```

④（`needs`）与 ⑤（`environment`）是「门禁」的两种形态：`needs` 让 job 按依赖链串行（坏代码到不了构建），`environment` 把发布动作挂到可审批的环境上——**CI 是自动的，发布可以是「门禁内自动」**。质量门禁之后是把新版本交给用户的方式——发布/部署策略对比（本阶段建立概念，编排层的落地属 K8s 独立专题）：

| 策略 | 回滚耗时 | 发布成本 | 适用场景 |
|------|---------|---------|---------|
| 滚动（rolling） | 长：逐批回滚 | 低：复用同一套实例 | 常态小版本 |
| 蓝绿（blue-green） | 短：流量切回旧环境 | 高：两套环境并行养着 | 大版本、回滚速度优先 |
| 金丝雀（canary） | 短：收回灰度流量 | 中：需分流 + 监控配合 | 高风险变更，先放 5% 试错 |


### 3.7 日志采集与监控：Prometheus 与 Grafana

**日志和监控是排障基础**（roadmap 必会概念）。部署形态的日志纪律：**应用往 stdout/stderr 写，收集交给环境**——systemd 收进 journald、Docker 收进容器日志（`docker logs`），再由采集器（Fluent Bit/Loki 等，概念级）汇聚。应用里直接写文件是反模式：容器文件系统随容器消失，日志必须外流。

监控侧，Prometheus 的模型是**拉（pull）**：监控服务端定期 HTTP 抓各实例的 `/metrics` 端点。四种指标类型：

| 类型 | 语义 | 例子 |
|------|------|------|
| Counter | 单调递增计数 | `health_requests_total`（请求总数） |
| Gauge | 可升可降的瞬时值 | `health_uptime_seconds`、当前连接数 |
| Histogram | 分布采样（分桶/count/sum） | `health_predict_seconds`（预测耗时） |
| Summary | 客户端算分位数 | 同上目的，聚合性差，少用 |

`/metrics` 端点手写最小实现（examples/ex05，已验证——起真实 uvicorn + httpx 断言）：打 3 次 `/predict` 后实测输出 `demo_requests_total{endpoint="predict"} 3`、`demo_predict_seconds_count 3`。生产用 `prometheus_client` 库，格式完全一致。

**Grafana 是看板与告警前端**——它自己不存指标，只把 Prometheus 当数据源查 PromQL 画图（project/ 的 compose 加了 prometheus 服务后，Grafana 接法三步）：

1. 加 `grafana/grafana` 服务进 compose，`depends_on` prometheus；
2. 数据源（Configuration → Data sources）选 Prometheus，**URL 填 `http://prometheus:9090`**——compose 内部网络里服务名即主机名（3.3），不要填 localhost；
3. 新建面板（Dashboards → New → Import）后写 PromQL 查询，下面是一组最小面板：

```promql
# 面板 1：请求速率（QPS）——Counter 必须先 rate() 才有意义，裸的单调计数只会画一条永不回落的线
rate(health_requests_total[1m])
# 面板 2：预测耗时 P95（Histogram 的桶 → histogram_quantile）
histogram_quantile(0.95, sum(rate(health_predict_seconds_bucket[5m])) by (le))
# 面板 3：当前推理后端（Gauge，label 是 joblib/rule/missing）
health_model_info
```

最小说明：`rate(...[1m])` 是「过去 1 分钟的平均增速」，秒级 QPS 的标准写法；`histogram_quantile` 需要 Histogram 的 `_bucket` 序列（手写版只有 count/sum，要 P95 得先换 `prometheus_client`，见 examples/ex05 文件头）。看板图只是第一步——**阈值 + 告警**（如 QPS 掉零持续 5 分钟）属告警前端（Alertmanager），本阶段概念到「看图」为止。

**服务要有健康检查**（roadmap 必会概念）是两种探针的分工（examples/ex01，已验证）：

- **liveness（/health）**：进程活着即 200——失败说明进程死了/卡死，守护层（compose/K8s）重启它；
- **readiness（/ready）**：依赖（模型/数据库）就绪才 200——失败说明「活着但不能接客」，负载均衡把流量切走但**不重启**。

ex01 实测了这对分工：故障注入（模型就绪标志翻转）后 `/ready → 503` 而 `/health` 仍 200——探活与摘流是两个动作，混为一谈会造成「数据库抖一下、全部实例被重启」的雪崩。

## 4. 底层原理

### 4.1 WSGI vs ASGI：两套服务器接口

Python Web 应用与服务器之间的标准接口经历了两代（ph10 的 4.1 从应用视角讲过协议直驱，这里从部署视角看选型后果）：

```python
# WSGI（2003，同步）：一个请求占用 worker 直到响应返回
def wsgi_app(environ, start_response):
    start_response("200 OK", [])
    return [b"ok"]

# ASGI（异步）：事件循环里挂起等待，worker 同时服务上千连接
async def asgi_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})
```

部署后果：**WSGI 应用的并发 = worker 进程数**（每个同步 worker 一次只能处理一个请求，等待数据库响应时整个 worker 干等）；**ASGI 应用的并发 = 事件循环的连接容量**（等待时挂起协程，worker 去服务别人）。这就是为什么 FastAPI 配 Uvicorn（ASGI 服务器），而 Gunicorn 管 ASGI 应用需要 `-k uvicorn.workers.UvicornWorker`——协议不匹配的组合起不来或跑成同步模式。WebSocket/SSE 等长连接在 WSGI 下根本不可行（一个连接独占一个 worker），是 ASGI 的立身之本。

### 4.2 多进程 worker 模型：pre-fork 与 GIL 的互补

GIL（ph14 详述）决定单个 Python 进程同一时刻只执行一个线程的字节码——**CPU 利用率的水平扩展只能靠多进程**。Gunicorn 的 pre-fork 模型：

```text
Gunicorn master（arbiter，不处理请求）
  │  fork                          ← 启动时按 --workers 数预派生
  ├── worker 1 ──▶ 处理请求（挂了？master 重新 fork）
  ├── worker 2 ──▶ 处理请求
  └── worker 3 ──▶ 处理请求
       ▲ 客户端连接由内核在监听 socket 的多个 worker 间分发
```

master 的职责是信号管理（`TERM` 优雅关停、`HUP` 重载配置、`TTIN/TTOU` 增减 worker）与 worker 心跳看护（worker 超时无响应就杀掉重拉——Gunicorn 自己就是个小守护进程）。worker 数量的经验公式：**同步 worker 约 2×CPU+1**（等 I/O 时 worker 空转，多配弥补）；**async worker（UvicornWorker）事件循环不吃这套**，常见 1×CPU 起步按延迟调。容器场景的等价物：`uvicorn --workers 4`（uvicorn 内置多进程 supervisor）或干脆「单进程 × N 个容器副本」——编排层做水平扩展与自愈，进程内不再嵌套进程管理（与 3.5 的判断规则一致）。

### 4.3 容器镜像分层：联合文件系统与构建缓存

镜像不是一个整文件，而是**一串只读层的叠加**（union filesystem）：每条 Dockerfile 指令产生一层，容器启动时在顶层加一个可写层（copy-on-write：改文件时先把原文件拷到可写层再改）。

```text
镜像（只读，自下而上叠加）                容器
┌─────────────────────────┐
│ 层4: COPY app.py        │ ← 改代码只重建这层    ┌──────────────┐
│ 层3: RUN pip install    │ ← requirements 变了才重建│ 可写层 (COW)  │
│ 层2: WORKDIR /app       │                     │  （随容器删）   │
│ 层1: FROM python:3.13-slim│ ← 与其他镜像共享   └──────────────┘
└─────────────────────────┘
```

两条直接推论：**① 构建缓存顺序**——`COPY requirements.txt` 必须在 `COPY app.py` 之前，否则改一行代码就让依赖层缓存失效、重装全部依赖（构建从 10 秒变 5 分钟）；**② 多阶段构建为什么镜像小**——`COPY --from=builder` 只把 venv 拷进最终镜像，builder 阶段的 pip 缓存、编译链、中间层全部留在 builder 阶段不带入。层共享还解释了「拉过 python:3.13-slim 的机器再拉任何基于它的镜像都很快」——基础层只存一份。

## 5. 使用场景

| 场景 | 选型 | 理由 |
|------|------|------|
| 单机定时脚本/爬虫 | 不用 Docker：venv + cron（或 systemd timer） | 没有「服务」要养，容器是纯开销 |
| 内部小工具/演示 | compose 单机（web+db 一把起） | 一条命令复现环境，够轻 |
| 生产 API（单机/小集群） | Nginx 反代 + uvicorn/gunicorn + systemd 守护 + /health + /metrics | 本阶段的完整栈，ex01~ex05 拼起来即是 |
| 生产 API（容器化） | Dockerfile 多阶段 + compose/K8s 编排 + Prometheus 抓取 | project/ 的模板形态 |
| 多实例弹性伸缩/自愈 | Kubernetes | 单机编排不够用时；本阶段只建概念地图，实战是独立专题 |
| 模型服务化 | joblib 产物 + FastAPI 包装 + 双探针（project/） | 训练与推理分离：产物随发布分发 |

**不适合此阶段的事项**：Kubernetes 实战（编排深入是独立专题）、Service Mesh/网关体系、多云与 IaC（Terraform）、日志中台（ELK/Loki 集群）——这些都在「单机到小规模」边界之外。

**上线前检查单**（把 3.1~3.7 收敛成"发布前最后一遍"）：每一项都来自正文的实测或结论——漏掉任何一项，它大概率会在上线后以故障的形式找回来。

- [ ] 依赖锁版本（`==`）、基础镜像非 `latest`（3.1/3.2——可复现的三抓手）
- [ ] 配置走环境变量、密钥走 secrets，代码里零配置（3.1/3.6）
- [ ] 服务有 `/health` 与 `/ready` 双探针，且两者语义分清（3.7——ready 503 时 health 仍 200）
- [ ] `/metrics` 有 Counter/Gauge 至少一种可观测（3.7）
- [ ] 日志写 stdout/stderr，由环境收集（3.7——应用写文件是反模式）
- [ ] 重启策略明确（systemd `Restart=on-failure` / compose `unless-stopped`，别用 `always` 无脑拉）（3.5）
- [ ] 静态资源/慢客户端有 Nginx 层挡着（3.4）
- [ ] 回滚预案：旧版本镜像/产物还在，能一键切回（3.6 策略表）

**上线后常见故障的排查路径**（症状 → 先查哪，全部指向本文章节）——与检查单是同一件事的两面：发布前用检查单堵住能预见的，发布后按症状查排障表快速定位剩下的：

| 症状 | 先查什么 | 定位 |
|------|---------|------|
| 服务起不来 | 进程在不在 → 端口被没被占 → 启动日志 | 3.1（`ps`/`lsof`/journalctl） |
| 起了但一直 503 | readiness 探针：依赖（模型/DB）就绪没 | 3.7（`/ready` 与 `depends_on` 健康依赖） |
| 请求很慢 | worker 数够不够（同步 worker 等 IO 空转）→ 有没有阻塞调用 | 3.4 / 4.2（worker 公式） |
| 偶发重启 | 退出形态：OOM？健康检查失败被摘？`Restart` 语义对不对 | 3.1 / 3.5 |
| 磁盘涨满 | 日志去哪了（journald 限额 / stdout 没外流） | 3.5 / 3.7 |
| 发布后行为不对 | 配置是不是旧环境变量 / 镜像是不是 `latest` 漂移 | 3.1 / 3.2 |
| HTTPS 报错/连接异常 | Nginx 证书路径与代理配置（`proxy_pass`/`ssl_*`） | 3.4 |

读表技巧：三列是"症状 → 先查的证据 → 机制章节"。多数故障按第二列的命令能在 30 秒内定位到"进程/端口/日志"这一层——那只是**现象层**；再往下问"为什么"（worker 数？事件循环被阻塞？健康检查语义？）就要翻到 4 章或对应 3.x 小节。排障的价值不在"修好"，在于把每次"为什么"补回这份表的第三列。

**与其他语言同类机制的对比**（一句话级，为 analysis/ 与 Tenet 合成积累素材）：Go 编译出**单静态二进制**，镜像可以 `FROM scratch` 做到十几 MB、启动毫秒级——Python 必须带解释器 + 依赖（slim 镜像也是百 MB 级），多阶段构建是在还这笔「解释型语言的部署税」；Java 同理要背 JVM。这解释了云原生基础设施为什么大量用 Go 写，而 Python 把部署复杂度用在「AI/数据服务的快速迭代」上才划算。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条验证。验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1；docker daemon 未启动 / macOS 无 systemd 的条目如实标注。

### 示例 1：FastAPI 服务与健康检查双探针（呼应 3.1/3.7，已验证）

完整文件 `examples/ex01-fastapi-health/`（`service.py` + `check_service.py`）：起真实 uvicorn 子进程 + httpx 断言。

```python
# examples/ex01-fastapi-health/service.py —— 双探针（已验证）
@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    if not _state["model_ready"]:
        response.status_code = 503          # 活着但不能接客：摘流不重启
        return {"status": "not ready"}
    return {"status": "ready"}
```

实测输出：`GET /health → 200 {"status": "ok"}`；`GET /ready → 200`；`POST /predict`（1500 次循环/25°C/DoD 80%/1C）→ `{"health": 80.5}`；故障注入后 `/ready → 503` 而 `/health` 仍 200；SIGTERM 后 `check_service.py` 断言退出码 -15（shell 143）并从捕获的 stderr 验证优雅关停日志 `INFO: Shutting down` 与 `INFO: Finished server process`（2026-09 复跑实测：uvicorn 0.50.0 优雅关停日志齐备后进程仍以 -15 被信号终止，断言按实测保留，与 ex05 unit 注释「systemd 视 SIGTERM 为正常停止」互相印证）。

### 示例 2：Dockerfile 多阶段构建（呼应 3.2/4.3，未在本环境验证）

完整文件 `examples/ex02-docker-multistage/`（Dockerfile + app.py + requirements.txt + .dockerignore）。

```dockerfile
# examples/ex02-docker-multistage/Dockerfile —— 未在本环境验证（docker daemon 未启动）
FROM python:3.13-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # 依赖层在代码层之前：缓存命中
FROM python:3.13-slim
COPY --from=builder /opt/venv /opt/venv              # 只带运行必需品
USER appuser
```

### 示例 3：Docker Compose 编排（呼应 3.3，语法已验证）

完整文件 `examples/ex03-docker-compose/docker-compose.yml`：web + postgres，`condition: service_healthy` 健康依赖、命名卷持久化、`restart: unless-stopped`。本机实测 `docker compose config` 离线解析通过；未实际 `up`（daemon 未启动）。

### 示例 4：Nginx 反向代理（呼应 3.4，语法已验证）

完整文件 `examples/ex04-nginx/nginx.conf`：upstream 池（max_fails 自动摘除）、静态分流、真实 IP 透传。本机实测 `nginx -t` → `syntax is ok` / `test is successful`（Homebrew nginx 1.31.2；`include mime.types` 按配置文件所在目录解析，验证时临时拷贝）。

### 示例 5：systemd unit 与 Prometheus /metrics 端点（呼应 3.5/3.7）

完整文件 `examples/ex05-systemd-metrics/`：unit 文件（**未在本环境验证**，macOS 无 systemd）+ 手写最小 Prometheus 端点（**已验证**）；Supervisor 等价配置在 `examples/ex05-supervisord/supervisord.conf`（呼应 3.5 对比，**未在本环境验证**——本机未装 Supervisor，supervisorctl 命令表见文件头）。

```python
# examples/ex05-systemd-metrics/service.py —— /metrics 文本格式（已验证）
lines += [
    "# TYPE demo_requests_total counter",
    f'demo_requests_total{{endpoint="{endpoint}"}} {count}',   # Counter 单调递增
    f"demo_predict_seconds_count {_hist['count']}",            # Histogram 骨架
]
```

实测输出（打 3 次 /predict 后）：`demo_requests_total{endpoint="predict"} 3`、`demo_predict_seconds_count 3`、`demo_uptime_seconds` Gauge 正常递增。

### 示例 6：GitHub Actions CI/CD 流水线（呼应 3.6，YAML 语法已验证）

完整文件 `examples/ex06-ci-cd.yml`：`on` 触发过滤（push main / pull_request / workflow_dispatch）→ concurrency 并发控制 → quality job（matrix 双 Python 版本、setup-python pip 缓存）→ `ruff check` → `pytest` → image job（`needs` 门禁 + `environment: production` 发布门禁）→ `docker build`，部署步骤以注释示意（secrets 只经 `${{ secrets.XXX }}` 引用，不写进 YAML）。本机 `yaml.safe_load` 解析通过；未推到 GitHub 实际运行。

## 7. 总结

### 关键要点

1. **部署环境要可复现**（必会概念）：锁依赖版本（`fastapi==0.139.1`）、锁基础镜像（`python:3.13-slim` 非 `latest`）——「半年后构建出同样的环境」是可复现的定义（3.1/3.2）
2. **配置与代码分离**（必会概念）：代码入库、配置进环境变量（MODEL_PATH / DATABASE_URL）；密钥走 secrets，绝不进 YAML/代码（3.1/3.6）
3. **容器 = 镜像 + 进程级隔离**：Dockerfile 每条指令一层，依赖层在代码层之前吃缓存；多阶段构建把编译链挡在最终镜像外（3.2/4.3）
4. **服务栈是三层分工**：Nginx 管连接层脏活（TLS/静态/限流/真实 IP），Gunicorn/uvicorn --workers 管进程，uvicorn worker 管 ASGI 事件循环——WSGI 并发看进程数，ASGI 并发看事件循环（3.4/4.1/4.2）
5. **进程守护三问**：挂了谁拉起（Restart=on-failure）、开机谁启动（WantedBy）、日志去哪（journald）；容器场景守护角色交给 compose/K8s，不要在容器里套守护进程（3.5）
6. **服务要有健康检查**（必会概念）：liveness 失败→重启，readiness 失败→摘流不重启——ex01 实测故障注入后 /ready 503 而 /health 200（3.7）
7. **日志和监控是排障基础**（必会概念）：日志写 stdout 由环境收集；Prometheus 拉模型抓 /metrics，Counter/Gauge/Histogram 各司其职；Grafana 画看板（3.7）
8. **CI/CD 是质量门禁链**：lint → test → build 任一红则止；secrets 不进仓库（3.6）
9. **验证纪律**：本机 daemon 未启动 / 无 systemd 的条目全部如实标注「未在本环境验证」，语法级能做的（compose config / nginx -t / yaml 解析）都做——部署笔记里最忌虚构「已验证」（第 2 章基线声明、各文件头验证块）
10. **上线前过检查单、上线后按症状查**：可复现/配置分离/双探针/日志外流/重启语义是发布前五查；起不来/503/慢/偶发重启各有先查路径（5 章清单与排障表）
11. **优雅关停是完整链路**：应用收 SIGTERM 收尾 → 守护层按退出形态决定拉起与否；无视 SIGTERM 会被升级 SIGKILL，连收尾机会都没有（3.1）

### 阶段验收清单

- [ ] 能说清「可复现环境」的三个抓手（锁版本依赖、固定基础镜像、声明式 compose）并解释 `latest` 的危害（对应 roadmap「能构建镜像」的心智部分）
- [ ] 能手写一个多阶段 Dockerfile 并说清「为什么 requirements 层在代码层之前」「为什么最终镜像里没有 pip 缓存」（对应 roadmap「能构建镜像」；本机 daemon 未启动，构建动作本身在 daemon 可用的机器上完成）
- [ ] 能部署一个带双探针的 FastAPI 服务并实测「readiness 503 时 liveness 仍 200」（对应 roadmap「能部署服务」，ex01/sol-01 已实测形态）
- [ ] 能用 compose 描述 web+db 的健康依赖编排，并说清 `depends_on` 不加 `condition: service_healthy` 的坑
- [ ] 能给服务写出 /metrics 端点并说清 Counter/Gauge/Histogram 的区别、Prometheus 拉模型的含义（对应 roadmap「能查看日志和指标」）
- [ ] 能写出 systemd unit 的三段结构并说清 `Restart=on-failure` 与 `always` 的区别（macOS 上如实标注未验证）
- [ ] 能独立跑通 6 个示例中标注「已验证」的条目并解释输出（第 6 章）；能跑通 project/ 的 `pytest` 与真实服务链路
- [ ] 能按 5 章"上线前检查单"逐项自检自己的服务，能按"排障路径表"描述常见故障的先查顺序

### 跨语言对比：部署形态

| 维度 | Python | Go | Java | Rust |
|------|--------|----|------|------|
| 交付物 | 代码 + 解释器 + 依赖（镜像百 MB 级） | 单静态二进制（可 FROM scratch，十几 MB） | jar + JVM（镜像百 MB 级） | 单二进制（接近 Go） |
| 进程模型 | 多进程 worker（GIL 所迫） | 单进程 goroutine | 单进程线程池 | 单进程 async/线程 |
| 启动速度 | 秒级（导入 + 加载产物） | 毫秒级 | 十秒级（JVM 预热） | 毫秒级 |
| 典型服务栈 | Nginx → Gunicorn/Uvicorn → app | 直接对外（net/http 够强）或网关 | 内嵌 Tomcat/Netty | 直接对外或网关 |

一句话：**解释型语言的部署税（镜像大、启动慢、多进程）是结构性的**——Python 用多阶段构建和分层缓存还这笔税，换回来的是 AI/数据生态的迭代速度（为 analysis/ 与 Tenet 合成积累素材：语言的运行时形态直接决定其部署形态）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。对应 roadmap 第 16 节「练习」小节四个题目：部署 FastAPI 服务（练习 1）、Docker Compose 启动服务和数据库（练习 2）、Nginx 反向代理（练习 3）、配置 systemd（练习 4），完成 4 题后继续：

- 部署 FastAPI 服务（★）：双探针 + lifespan 依赖加载 + Pydantic 校验，TestClient 实测
- Docker Compose 启动服务和数据库（★★）：健康依赖 + 数据卷 + 配置入环境变量
- Nginx 反向代理（★★）：upstream 池 + 真实 IP 透传 + 限流 + WebSocket 头
- 配置 systemd（★★）：unit 三段 + 崩溃拉起 + 安全加固（macOS 上标注未验证）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**部件健康预测服务部署模板（health-api）**——把 ph15 的「joblib 产物 + cli.py 命令行推理」升级为带 `/health`、`/ready`、`/predict`、`/metrics` 四端点的 FastAPI 服务，配多阶段 Dockerfile、Compose（服务 + Prometheus 抓取）编排；7 个 pytest 用例 + ruff 全绿 + 真实 uvicorn 链路实测（对应 roadmap「推荐项目」第一个「FastAPI 部署模板」；第二个「数据服务 Docker Compose」由 examples/ex03 与 project 的 compose 覆盖）。建议完成练习后再动手，练习 1（可部署服务形态）是它的缩小版。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`python3 -m pytest` → 7 passed；`ruff check .` 全绿；`python3 train.py` 产出物并自检；uvicorn 起服务实测 `/ready` 报 `model_type: joblib`、`/predict` 返回合理 HEALTH；ph15 的 `ComponentHealthPipeline` 产物**形态**兼容通过 project 测试 `test_ph15_pipeline_artifact_compat`——stub 级验证，真实 ph15 产物需其 `health` 包可导入，见 project/README 扩展方向）

### 下一阶段

[高级 Python 阶段](../ph17-advanced-python/17-advanced-python.md) — 部署视角的「服务能跑」之后，回到语言本身往深处走：迭代器/生成器/装饰器的底层协议、描述符与元类、GIL 为什么存在与垃圾回收机制（本阶段 4.2 只用到「GIL 逼出多进程」这一结论，ph17 讲清它为什么存在与何时切换）、协程原理与 C 扩展。届时你会重新理解本阶段的两个「为什么」：uvicorn 的事件循环为什么能一个进程服务上千连接（协程原理，ph17 的 3.9/4.4），以及「单进程 × 多容器副本」与「多进程 worker」之争背后的 GIL 权衡。
