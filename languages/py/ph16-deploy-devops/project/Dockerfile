# project/Dockerfile —— 部署模板的多阶段构建
# 验证环境目标：Docker Engine 29 / 镜像基线 python:3.13-slim
# 验证状态：未在本环境验证（本机 docker CLI 在、daemon 未启动，无法 build）——
#   在 daemon 可用的机器上按 README「容器化运行」一节验证
# 构建：docker build -t bhealth-api:0.1.0 .

# ---------- 阶段 1：builder（装依赖；pip 缓存/编译链不进最终镜像） ----------
FROM python:3.13-slim AS builder
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# 先拷依赖清单再装：依赖没变这层缓存就命中（镜像分层原理见主文档 4.3）
# scikit-learn 是加载 joblib 产物的运行期依赖（产物是 sklearn 对象）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- 阶段 2：runtime（只带运行必需） ----------
FROM python:3.13-slim
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/
ENV PATH="/opt/venv/bin:$PATH"
# 模型产物不烤进镜像：发布时挂载/下载到 /models，环境变量指过去（配置与代码分离）
ENV MODEL_PATH=/models/model.joblib
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
