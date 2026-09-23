#!/usr/bin/env python3
"""部件健康预测命令行入口（project/cli.py）。

流程：合成部件老化数据 → train/test 划分 → HEALTH 回归 + 等级分类 → 指标 →
模型产物写盘（默认 /tmp/health-model/model.joblib）→ 可选：加载模型做单条预测。

用法：
    python3 cli.py --demo                 # 离线自检（小样本、断言全过、产物写 /tmp）
    python3 cli.py                        # 默认 N=1500 完整训练 + 指标 + 保存产物
    python3 cli.py --predict 1500 25 80 1.0     # 加载已保存模型预测一组合况
    python3 cli.py --n 600 --out /tmp/health-model --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from health.data import GRADE_NAMES, load_component_data
from health.evaluate import summary_metrics
from health.model import ComponentHealthPipeline, train_pipeline

DEFAULT_OUT = Path("/tmp/health-model")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="部件健康预测（HEALTH 回归 + 健康等级分类）")
    parser.add_argument("--n", type=int, default=1500, help="合成数据量（默认 1500）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="模型产物目录（默认 /tmp/health-model）"
    )
    parser.add_argument(
        "--predict",
        nargs=4,
        type=float,
        metavar=("CYCLES", "TEMP", "DEPTH", "CRATE"),
        help="加载已保存模型预测 HEALTH 与等级（4 个工况值）",
    )
    parser.add_argument(
        "--demo", action="store_true", help="离线自检（小样本训练 + 断言 + 产物写 /tmp）"
    )
    return parser.parse_args(argv)


def run_train(args: argparse.Namespace) -> ComponentHealthPipeline:
    """合成数据 → 训练 → 指标 → 产物落盘，返回管线。"""
    data = load_component_data(n=args.n, seed=args.seed)
    train, test = data.split(test_size=args.test_size, seed=args.seed)
    pipeline = train_pipeline(train)
    metrics = summary_metrics(pipeline, train, test)
    path = pipeline.save(args.out)
    print(
        f"训练 {metrics['n_train']} / 测试 {metrics['n_test']} 组部件；"
        f"等级分布 {metrics['grade_dist_test']}"
    )
    print(
        f"HEALTH 回归:   RMSE {metrics['regression']['rmse']:.3f}%  "
        f"MAE {metrics['regression']['mae']:.3f}%"
        f"  R² {metrics['regression']['r2']:.3f}（baseline 预测均值 RMSE "
        f"{metrics['baselines']['reg_rmse_mean_pred']:.2f}%）"
    )
    print(
        f"等级分类:   acc {metrics['classification']['accuracy']:.3f}  macro-F1 "
        f"{metrics['classification']['macro_f1']:.3f}（baseline 多数类 acc "
        f"{metrics['baselines']['clf_acc_majority']:.3f}）"
    )
    print(f"混淆矩阵:   {metrics['confusion_matrix']}")
    print(f"模型产物:   {path}（模型 + 特征名 + 元信息，joblib 序列化）")
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return pipeline


def run_predict(args: argparse.Namespace) -> None:
    """加载模型做单条预测（模型部署的最小闭环：跨进程推理）。"""
    path = args.out / "model.joblib"
    if not path.exists():
        print(f"模型不存在: {path} —— 先运行 python3 cli.py 训练一次", file=sys.stderr)
        raise SystemExit(2)
    pipeline = ComponentHealthPipeline.load(path)
    cycles, temp, depth, crate = args.predict
    x = np.array([[cycles, temp, depth, crate]])
    health = float(pipeline.predict_health(x)[0])
    grade = int(pipeline.predict_grade(x)[0])
    print(f"工况: {cycles:.0f} 次循环 / {temp:.0f}°C / DoD {depth:.0f}% / {crate:.1f}C")
    print(f"预测 HEALTH: {health:.1f}%  → 健康等级: {GRADE_NAMES[grade]}")


def run_demo(args: argparse.Namespace) -> None:
    """离线自检：小样本训练，指标断言（回归 R²、分类 acc 下限），产物写 /tmp。"""
    if args.n == 1500:  # 没显式指定样本量时用小样本快速自检
        args.n = 400
    if args.out == DEFAULT_OUT:  # 产物纪律：demo 产物固定写 /tmp/health-demo
        args.out = Path("/tmp/health-demo")
    pipeline = run_train(args)
    data = load_component_data(n=args.n, seed=args.seed)
    _train, test = data.split(test_size=args.test_size, seed=args.seed)
    metrics = summary_metrics(pipeline, _train, test)
    assert metrics["regression"]["r2"] > 0.85, "HEALTH 回归 R² 应 > 0.85"
    assert metrics["classification"]["accuracy"] > 0.75, "等级分类 acc 应 > 0.75"
    print(
        "\n自检通过：R² {:.3f} > 0.85、acc {:.3f} > 0.75、产物已写 /tmp/health-demo".format(
            metrics["regression"]["r2"], metrics["classification"]["accuracy"]
        )
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.predict is not None:
        run_predict(args)
    elif args.demo:
        run_demo(args)
    else:
        run_train(args)


if __name__ == "__main__":
    main()
