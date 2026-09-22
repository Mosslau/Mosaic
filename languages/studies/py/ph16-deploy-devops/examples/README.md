# examples —— 部署与 DevOps 阶段完整示例

> 每个示例对应主文档 `16-deploy-devops.md` 相关小节（3.1~3.7）的完整可用版。验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1（本机已装并实测）；Docker CLI 29.6.2 在但 **daemon 未启动**；Homebrew nginx 1.31.2；**macOS 无 systemd**——各示例的验证级别如实标注在下表与文件头。

| 文件 | 说明 | 运行 / 验证 |
|------|------|------------|
| `ex01-fastapi-health/service.py` | FastAPI 服务 + 双探针健康检查（/health liveness、/ready readiness）+ 最小推理端点 + 故障注入（主文档 3.1/3.7） | 手动：`python3 -m uvicorn service:app --port 8016` |
| `ex01-fastapi-health/check_service.py` | 起真实 uvicorn 子进程 + httpx 断言健康检查/就绪/推理/故障切换/SIGTERM 关停 | `python3 check_service.py`（离线，已验证） |
| `ex02-docker-multistage/` | 多阶段构建 Dockerfile（builder/runtime 分离、缓存顺序、非 root）+ 最小 app + .dockerignore（主文档 3.2/4.3） | 未在本环境验证（daemon 未启动）；daemon 可用时 `docker build -t ex02-demo .` |
| `ex03-docker-compose/docker-compose.yml` | web + postgres 编排：健康依赖、数据卷、restart（主文档 3.3） | 语法已验证（`docker compose config` 离线解析通过）；未实际启动 |
| `ex04-nginx/nginx.conf` | Nginx 反代完整配置：upstream 池、静态分流、真实 IP 透传（主文档 3.4） | 语法已验证（本机 `nginx -t` 通过，mime.types 需在 conf 同目录）；未起真实链路 |
| `ex05-systemd-metrics/bhealth-api.service` | systemd unit：开机自启、崩溃拉起、日志进 journald（主文档 3.5） | 未在本环境验证（macOS 无 systemd） |
| `ex05-supervisord/supervisord.conf` | Supervisor 等价守护配置（INI；supervisorctl 命令表见文件头，主文档 3.5） | 未在本环境验证（本机未装 Supervisor） |
| `ex05-systemd-metrics/service.py` + `check_metrics.py` | 手写最小 Prometheus /metrics 端点（Counter/Histogram/Gauge）+ 实测验证（主文档 3.7） | `python3 check_metrics.py`（离线，已验证） |
| `ex06-ci-cd.yml` | GitHub Actions 流水线：触发过滤 + concurrency + matrix + quality/image 门禁 → lint → test → 镜像构建（主文档 3.6） | YAML 语法已验证（本机 yaml.safe_load 解析通过）；未推到 GitHub 实际运行 |
| `pyproject.toml` | 本目录 ruff 校验基准（line-length 100、select E/F/I/UP/B） | 被 `ruff check` 命令自动读取（本机实测全绿） |

说明：

- **已验证的两个服务示例**（ex01/ex05）都是「起真实 uvicorn 子进程 + httpx 客户端断言」的完整链路，不是 TestClient 模拟——这就是「部署后第一件事：打健康检查」的自动化形态
- **配置类示例**（Dockerfile/compose/nginx/systemd/CI）因本机环境限制只有语法级验证或未验证——文件头逐一标注；在 Linux + Docker daemon 的机器上请按文件头命令实际验证
- **产物纪律**：示例不起后台残留进程（check 脚本 finally 里 SIGTERM 关停）、不落盘产物——运行后 `git status` 工作区干净

验证状态（本机实测输出）：

- `ex01`：`GET /health → 200 {"status": "ok"}`；`GET /ready → 200`；`POST /predict`（1500 次循环/25°C/DoD 80%/1C）→ `{"soh": 80.5}`；故障注入后 `/ready → 503` 而 `/health` 仍 200；SIGTERM 后退出码 -15（shell 143），脚本从捕获的 stderr 断言优雅关停日志（`INFO: Shutting down` / `INFO: Finished server process`）
- `ex03`：`docker compose config` 离线解析通过（daemon 未启动，未实际 `up`）
- `ex04`：`nginx -t` → `syntax is ok` / `test is successful`（Homebrew nginx 1.31.2）
- `ex05`：打 3 次 /predict 后 `/metrics` 实测输出 `demo_requests_total{endpoint="predict"} 3`、`demo_predict_seconds_count 3`、`demo_uptime_seconds` Gauge 正常
- `ex06`：`python3 -c "import yaml; yaml.safe_load(...)"` 解析通过
