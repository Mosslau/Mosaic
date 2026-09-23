# examples/ex02-docker-multistage/app.py —— 多阶段构建要打包的最小 FastAPI 应用
# 与 ex01 的服务同形（/health + /predict 规则模型），独立一份保证本目录可单独构建。
from fastapi import FastAPI

app = FastAPI(title="ex02-docker-demo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/predict")
def predict(cycles: float = 1500) -> float:
    """最简规则模型：HEALTH = 100 - 0.008 * cycles（占位，真实模型见 ../../project/）。"""
    return round(max(40.0, 100.0 - 0.008 * cycles), 1)
