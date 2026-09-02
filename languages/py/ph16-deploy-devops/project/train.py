#!/usr/bin/env python3
"""模型产物生产脚本（ph16 project/train.py）。

服务化的分工：训练发生在 CI/训练机（本脚本），产物（joblib）随发布分发，
服务进程只加载不训练（app/predictor.py 的 JoblibPredictor）。

用法：
    python3 train.py                          # 产物写 /tmp/bhealth-api-model/model.joblib
    python3 train.py --out /tmp/x --n 800     # 自定义输出目录与样本量
    MODEL_PATH=/tmp/bhealth-api-model/model.joblib \
        python3 -m uvicorn app.main:app --port 8000

产物纪律：默认写 /tmp，不入库（.dockerignore 与仓库 .gitignore 均排除 *.joblib）。
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_OUT = Path("/tmp/bhealth-api-model")


def train(n: int = 800, seed: int = 42) -> object:
    """合成电池老化数据（与 app/predictor.py 规则公式同源 + 噪声），训练随机森林。"""
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor

    rng = np.random.default_rng(seed)
    cycles = rng.uniform(100, 3200, n)
    avg_temp = rng.uniform(18, 45, n)
    depth = rng.uniform(40, 100, n)
    c_rate = rng.uniform(0.3, 2.2, n)
    X = np.column_stack([cycles, avg_temp, depth, c_rate])
    loss = (
        0.008
        + 0.00025 * np.maximum(avg_temp - 25, 0)
        + 0.0005 * np.maximum(depth - 70, 0)
        + 0.0015 * np.maximum(c_rate - 1.5, 0)
    )
    soh = np.clip(100 - cycles * loss + rng.normal(0, 1.2, n), 40, 100)
    return RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=-1).fit(X, soh)


def main() -> None:
    parser = argparse.ArgumentParser(description="训练电池 SOH 模型并落盘 joblib 产物")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="产物目录（默认 /tmp）")
    parser.add_argument("--n", type=int, default=800, help="合成样本量")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    import joblib

    model = train(n=args.n, seed=args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "model.joblib"
    joblib.dump(model, path)
    # 自检：同条件加载回来能预测（部署前最后一道防线）
    loaded = joblib.load(path)
    probe = float(loaded.predict([[1500, 25, 80, 1.0]])[0])
    print(f"产物: {path}（{path.stat().st_size / 1024:.0f} KiB）")
    print(f"自检: predict([1500, 25, 80, 1.0]) = {probe:.1f}%（规则公式参考值 80.5%）")


if __name__ == "__main__":
    main()
