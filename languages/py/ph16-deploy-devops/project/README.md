# ph16 阶段项目：电池健康预测服务部署模板（bhealth-api）

> 对应 roadmap 第 16 节「推荐项目」第一个「FastAPI 部署模板」——把 ph15 项目（[`../../ph15-ai-ml/project/`](../../ph15-ai-ml/project/)）的「joblib 产物 + cli.py 命令行推理」升级为「可部署的 HTTP 服务」：双探针健康检查 + Prometheus 指标端点 + 环境变量注入模型产物 + 多阶段 Dockerfile + Compose 编排（服务 + Prometheus 抓取）。另一个推荐项目「数据服务 Docker Compose」由 [`../examples/ex03-docker-compose/`](../examples/ex03-docker-compose/) 与本项目的 `docker-compose.yml` 覆盖。

## 需求

ph15 的模型交付止步于「另一个进程能加载产物做预测」（命令行）。生产要的是：**模型变成一个长期存活、可探活、可观测、可重建的服务**。本模板把这件事的最小闭环做出来：

- **服务化**：`POST /predict` 输入电池工况（循环次数/温度/放电深度/充电倍率），返回 SOH 与健康等级——推理后端有两档：加载 joblib 产物（`JoblibPredictor`，ph15 产物的消费方式）或规则公式兜底（`RulePredictor`，无产物也能起服务）；
- **可探活**：`/health`（liveness）与 `/ready`（readiness）分工——配置了 `MODEL_PATH` 但产物缺失时 `/ready` 与 `/predict` 都返回 503，**不静默降级**（把「模型没挂上」藏成「服务正常」是生产事故的经典开局）；
- **可观测**：`/metrics` 手写最小 Prometheus 文本格式（请求计数、预测耗时、当前推理后端、运行时长），compose 里带 Prometheus 抓取配置；
- **可重建**：多阶段 Dockerfile（构建期与运行期分离、非 root 运行、产物不烤进镜像）+ Compose 一键起「服务 + 监控」。

## 功能清单

- [x] `app/predictor.py`：`Predictor` 协议 + 规则兜底/Joblib 双后端；`MODEL_PATH` 语义：未设置→规则兜底，设置了但缺失→不就绪
- [x] `app/main.py`：应用工厂 `create_app()`；lifespan 加载依赖；`/health` `/ready` `/predict` `/metrics` 四端点；请求计数中间件
- [x] `app/metrics.py`：进程内最小指标注册表（Counter/Histogram/Gauge，Prometheus 文本格式）
- [x] `train.py`：训练 SOH 随机森林并落盘 joblib 产物（默认写 `/tmp/bhealth-api-model/`，产物不入库），含加载自检
- [x] `tests/test_api.py`：6 个 pytest 用例（探针分工、422 校验、规则推理、指标格式、产物缺失 503、训练产物闭环）
- [x] `Dockerfile` + `.dockerignore` + `requirements.txt`：多阶段构建、锁版本、非 root
- [x] `docker-compose.yml` + `prometheus.yml`：服务 + Prometheus 抓取编排
- [x] 质量门禁：`ruff check .` 与 `ruff format --check .` 全绿

## 验收标准

- `python3 -m pytest` → **6 passed**（本机实测，2.2s）
- `ruff check .` → `All checks passed!`；`ruff format --check .` → 6 files already formatted（本机实测）
- `python3 train.py` → 产物 `/tmp/bhealth-api-model/model.joblib`（本机实测 13953 KiB），加载自检 `predict([1500, 25, 80, 1.0]) = 78.6%`（规则公式参考值 80.5%）
- 真实服务链路（本机实测，uvicorn + httpx）：`MODEL_PATH=/tmp/bhealth-api-model/model.joblib python3 -m uvicorn app.main:app` 起服务后——`GET /ready` → `{"status": "ready", "model_type": "joblib"}`；`POST /predict`（1500 次循环/25°C/DoD 80%/1C）→ `soh 78.6 / 临界`；`GET /metrics` → `bhealth_model_info{model_type="joblib"} 1`、`bhealth_predict_seconds_count` 随请求递增
- **产物纪律**：joblib 产物写 `/tmp` 或由卷挂载，不入库；运行后 `git status` 工作区干净
- **未在本环境验证**（如实标注）：`docker build` / `docker compose up`（本机 daemon 未启动——compose 文件已做 `docker compose config` 离线语法验证）；Prometheus 实际抓取（同理）；systemd 部署（macOS 无 systemd，unit 示例见 [`../examples/ex05-systemd-metrics/`](../examples/ex05-systemd-metrics/)）

## 运行手册

```bash
# 1. 训练产物（在训练机/CI 上做，产物随发布分发）
python3 train.py

# 2a. 裸机运行（开发/小部署）
MODEL_PATH=/tmp/bhealth-api-model/model.joblib \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

# 2b. 容器化运行（daemon 可用的机器上；本机未验证）
docker build -t bhealth-api:0.1.0 .
docker run --rm -p 8000:8000 -v /tmp/bhealth-api-model:/models:ro bhealth-api:0.1.0

# 2c. Compose 起服务 + Prometheus（daemon 可用的机器上；本机只验证语法）
docker compose up -d --build

# 3. 验证
curl http://127.0.0.1:8000/ready
curl -X POST http://127.0.0.1:8000/predict \
    -H 'content-type: application/json' \
    -d '{"cycles": 1500, "avg_temp": 25, "depth": 80, "c_rate": 1.0}'
curl http://127.0.0.1:8000/metrics
```

## 扩展方向

- **接 ph15 的真模型**：本模板的规则公式与 ph15 合成数据同源，把 `train.py` 换成 ph15 的 `BatteryHealthPipeline` 产物即可服务化真模型（注意产物版本与服务代码版本要一起发布）
- **接 Nginx 反代与 systemd**：examples/ 的 ex04/ex05 配置就是为本模板准备的，组合起来是完整的单机生产形态
- **Grafana 看板**：compose 加 `grafana/grafana` 服务，数据源指向 prometheus，画出 `rate(bhealth_requests_total[1m])` 与预测耗时（主文档 3.7）
- **CI/CD 流水线**：examples/ 的 ex06 工作流为本模板跑 ruff/pytest/build，镜像推到制品库后触发部署
