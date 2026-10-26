"""参考解 06（迁移）：分布漂移下的分割鲁棒性（高斯噪声）。

运行：cd exercises && uv run python sol-06-噪声鲁棒性.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from baseline import PixelLogistic  # noqa: E402
from demo import load_data, score, train_tinyunet  # noqa: E402


def add_noise(X: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(X + rng.normal(0.0, sigma, size=X.shape), 0.0, 1.0)


def main() -> None:
    data = load_data()
    model, seconds = train_tinyunet(data)
    lr_model = PixelLogistic().fit(*data["train"])
    Xte, Yte = data["test"]
    print(f"TinyUNet 训练 {seconds:.1f}s；在测试图上加不同强度的高斯噪声：")
    print(f"{'sigma':>5} | {'方法':16} | {'pixel acc':>9} | {'IoU':>6} | {'Dice':>6}")
    print("-" * 58)
    rows = []
    for sigma in (0.0, 0.05, 0.10, 0.20):
        Xn = add_noise(Xte, sigma, seed=100 + int(sigma * 100))
        cnn = score(model.predict(Xn), Yte)
        lr = score(lr_model.predict(Xn), Yte)
        rows.append((sigma, cnn, lr))
        for name, metrics in (("TinyUNet", cnn), ("像素逻辑回归", lr)):
            print(f"{sigma:5.2f} | {name:16} | {metrics['pixel_acc']:9.4f} | "
                  f"{metrics['iou']:6.4f} | {metrics['dice']:6.4f}")
    clean_iou = rows[0][1]["iou"]
    noisy_iou = rows[1][1]["iou"]
    assert clean_iou > 0.8, "干净测试集上应先达到可用水平"
    assert noisy_iou < clean_iou - 0.2, "应观察到明显的分布漂移衰减"
    assert rows[1][2]["iou"] > noisy_iou, "本实验的结论是：无增广的 CNN 被像素基线反超"
    print(f"\nσ=0.05 时 TinyUNet IoU {clean_iou:.4f} → {noisy_iou:.4f}；"
          f"像素基线 {rows[0][2]['iou']:.4f} → {rows[1][2]['iou']:.4f}。")
    print("→ 结论：深度模型不会自动鲁棒。只在干净图上训练时，σ=0.05 的像素噪声")
    print("  就让 IoU 腰斩，甚至被只看灰度的基线反超；部署前应做噪声增广/域适应。")


if __name__ == "__main__":
    main()
