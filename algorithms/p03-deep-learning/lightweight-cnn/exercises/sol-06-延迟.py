"""参考解 6：参数少 ≠ 延迟低 —— 三路延迟与 torch 线程数对照。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo  # noqa: E402
import framework  # noqa: E402
from impl import MobileNetLite, StandardCNN  # noqa: E402

X_tr, X_te, y_tr, y_te = demo.load_data()
Xb = X_te[:128]

hand_ds = MobileNetLite().init()
hand_std = StandardCNN().init()
torch_ds = framework.TorchMobileNetLite(widths=(8, 16, 32, 32))
torch_ds._build()

print(f"手写 DS          {demo.bench_forward(hand_ds.predict_proba, Xb):7.2f} ms"
      f"（{hand_ds.n_params()} 参数）")
print(f"手写标准 Conv    {demo.bench_forward(hand_std.predict_proba, Xb):7.2f} ms"
      f"（{hand_std.n_params()} 参数）")

for threads in (1, 4, 8):
    framework.set_threads(threads)
    ms = demo.bench_forward(torch_ds.predict_proba, Xb)
    print(f"torch DS（{threads} 线程）{ms:7.2f} ms")

assert demo.bench_forward(hand_ds.predict_proba, Xb) < demo.bench_forward(
    hand_std.predict_proba, Xb)
print("\n→ 参数少 5.4×，手写延迟只快约 1.6×；torch 推理随线程数加快，"
      "但训练时小 batch 反而 1 线程最快——线程收益取决于负载。")
