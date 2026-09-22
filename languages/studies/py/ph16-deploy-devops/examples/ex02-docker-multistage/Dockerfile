# examples/ex02-docker-multistage/Dockerfile —— 多阶段构建：构建期与运行期分离
# 验证环境目标：Docker Engine 29 / 镜像基线 python:3.13-slim
# 验证状态：未在本环境验证（本机 docker CLI 29.6.2 在、daemon 未启动，无法 build）——
#   指令与多阶段写法按 Docker 官方文档；在 daemon 可用的机器上按下方命令验证
# 构建与运行（在 daemon 可用的机器上）：
#   # 1. 构建镜像（构建缓存教学点：requirements 层在代码层之前，改代码不重装依赖）
#   docker build -t ex02-demo:0.1.0 .
#   # 2. 运行容器（宿主机 8000 → 容器 8000）
#   docker run --rm -p 8000:8000 ex02-demo:0.1.0
#   # 3. 打健康检查
#   curl http://127.0.0.1:8000/health

# ---------- 阶段 1：builder（装依赖；gcc/缓存等构建期产物不进最终镜像） ----------
FROM python:3.13-slim AS builder
WORKDIR /build
# venv 隔离依赖，最终镜像整目录拷贝——比 pip install 到系统 site-packages 更干净
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# 先拷 requirements 再装依赖：只要 requirements 没变，这层缓存就命中（见主文档 4.3）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- 阶段 2：runtime（只拿运行必需的东西，镜像最小） ----------
FROM python:3.13-slim
# 非 root 运行：容器逃逸时的第二道防线
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app.py .
ENV PATH="/opt/venv/bin:$PATH"
USER appuser
EXPOSE 8000
# 容器内监听 0.0.0.0（容器有自己的网络命名空间，127.0.0.1 只对容器内部可达）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
