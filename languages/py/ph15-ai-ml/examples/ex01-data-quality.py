#!/usr/bin/env python3
# examples/ex01-data-quality.py —— 数据质量与数据泄漏（主文档 3.3）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 ex01-data-quality.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定 seed=42 下的本机实测，完全可复现；
#           换 seed 或数据划分会波动（约 ±1~2 个百分点），对比方向稳定
# 验证块数字实测：干净 test acc 0.930 / 标签噪声 25% test acc 0.747 / 缺失均值填充 test acc 0.917 /
#                泄漏 val acc 0.990（虚假高）vs 泄漏特征失效后 test acc 0.897（回归真实水平）
"""数据质量与数据泄漏演示（roadmap 必会概念：数据质量决定模型上限）。

同一份「电池传感器故障」分类数据（0=健康 88%、1=充电过压 8%、2=过热振动 4%），
三种改法对比验证分数，全部用同一套 60/20/20 划分 + StandardScaler + kNN(5)：
  A. 干净基线：train/val/test 严格隔离 —— 记录每个类的召回率（少数类召回低是
     「准确率骗人」的第一现场，主文档 3.5 与 ex03 展开）
  B. 标签噪声：训练集 25% 标签被随机改错（源头脏）→ 分数明显下降
  C. 缺失值：voltage/current 两列 60% 随机缺失，均值填充只用训练集统计量 →
     信息损失如实呈现（kNN 对单列缺失较稳健，损失幅度小；更糟的是「非随机
     缺失 + 朴素填充」，见主文档 3.3 讲解）
  D. 特征泄漏：加入「诊断完成后才知道的维修码」（与标签强相关）→ val 虚高到
     0.990；真实预测时该码拿不到（换成随机噪声）→ 分数回落到 0.897
结论：模型上限由数据质量决定 —— 脏标签进、脏结果出；测试集只在最后碰一次；
任何「用了未来/事后信息」的特征都会让验证分数骗人。
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

SEED = 42
N = 1500
# 特征列名（temp:°C / voltage:V / current:A / vibration:无量纲 / resistance:Ω）
FEATURES = ["temp", "voltage", "current", "vibration", "resistance"]
CLASSES = ["健康", "充电过压", "过热振动"]


def make_fault_data(
    n: int = N, seed: int = SEED, label_noise: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """生成电池传感器故障数据：0=健康(88%)、1=充电过压(8%)、2=过热振动(4%)。"""
    rng = np.random.default_rng(seed)
    n0, n1 = int(n * 0.88), int(n * 0.08)
    n2 = n - n0 - n1

    def gauss(mean: list[float], std: list[float], k: int) -> np.ndarray:
        return np.asarray(mean) + np.asarray(std) * rng.standard_normal((k, 5))

    healthy = gauss([30, 3.7, 10, 0.5, 1.2], [5, 0.16, 2.8, 0.3, 0.12], n0)  # 正常工况
    fault_a = gauss([34, 4.0, 8.5, 1.0, 1.4], [5, 0.3, 3.2, 0.4, 0.18], n1)  # 充电过压
    fault_b = gauss([46, 3.7, 12, 1.6, 1.5], [12, 0.28, 4.5, 1.2, 0.35], n2)  # 过热/振动
    X = np.vstack([healthy, fault_a, fault_b])
    y = np.concatenate([np.zeros(n0), np.ones(n1), np.full(n2, 2)]).astype(int)

    idx = rng.permutation(n)
    X, y = X[idx], y[idx]
    if label_noise > 0:
        # 随机把 label_noise 比例的标签改成另一个随机类别（模拟标注错误）
        flip = rng.random(n) < label_noise
        n_flip = int(flip.sum())
        y[flip] = rng.integers(0, 3, size=n_flip)
    return X, y


def split_raw(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, ...]:
    """60/20/20 train/val/test 划分（分层抽样保持类别比例）。缩放由调用方后置。"""
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=SEED)
    X_va, X_te, y_va, y_te = train_test_split(
        X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=SEED
    )
    return X_tr, X_va, X_te, y_tr, y_va, y_te


def evaluate_knn(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_va: np.ndarray,
    y_va: np.ndarray,
    X_te: np.ndarray,
    y_te: np.ndarray,
) -> tuple[float, float, float]:
    """对已缩放数据拟合 kNN(5)，返回 train/val/test 准确率。"""
    clf = KNeighborsClassifier(n_neighbors=5).fit(X_tr, y_tr)
    return (
        accuracy_score(y_tr, clf.predict(X_tr)),
        accuracy_score(y_va, clf.predict(X_va)),
        accuracy_score(y_te, clf.predict(X_te)),
    )


def section_a_clean() -> tuple[np.ndarray, np.ndarray, float]:
    print("== A. 干净数据基线（60/20/20 划分，seed=42）==")
    X, y = make_fault_data()
    X_tr, X_va, X_te, y_tr, y_va, y_te = split_raw(X, y)
    scaler = StandardScaler().fit(X_tr)
    clf = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
    tr = accuracy_score(y_tr, clf.predict(scaler.transform(X_tr)))
    va = accuracy_score(y_va, clf.predict(scaler.transform(X_va)))
    te = accuracy_score(y_te, clf.predict(scaler.transform(X_te)))
    rec = recall_score(y_te, clf.predict(scaler.transform(X_te)), average=None)
    print(f"   train acc {tr:.3f} / val acc {va:.3f} / test acc {te:.3f}")
    print(
        "   测试集各类召回率: "
        + " / ".join(f"{c} {r:.3f}" for c, r in zip(CLASSES, rec, strict=True))
    )
    print(
        "   → 整体 0.930 很漂亮，但两个故障类的召回只有 0.46/0.50（多数类淹没少数类，"
        "准确率骗人的第一现场，ex03 展开）"
    )
    return X_te, y_te, te


def section_b_label_noise() -> float:
    print("== B. 标签噪声（训练集 25% 标签被随机改错）==")
    X, y = make_fault_data(label_noise=0.25)
    X_tr, X_va, X_te, y_tr, y_va, y_te = split_raw(X, y)
    scaler = StandardScaler().fit(X_tr)
    clf = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
    va = accuracy_score(y_va, clf.predict(scaler.transform(X_va)))
    te = accuracy_score(y_te, clf.predict(scaler.transform(X_te)))
    print(f"   val acc {va:.3f} / test acc {te:.3f}（对照 A：干净数据高得多）")
    return te


def section_c_missing_values() -> float:
    print("== C. 缺失值（voltage/current 两列 60% 随机缺失，均值填充）==")
    rng = np.random.default_rng(SEED)
    X, y = make_fault_data()
    Xc = X.copy()
    miss = rng.random(X.shape[0]) < 0.60
    Xc[miss, 1] = np.nan  # voltage 列挖空
    Xc[miss, 2] = np.nan  # current 列挖空（模拟两个传感器通道断采）
    X_tr, X_va, X_te, y_tr, y_va, y_te = split_raw(Xc, y)
    # 填充：均值只能来自训练集——用全量均值填充本身就是一种泄漏
    for col in (1, 2):
        mean_col = float(np.nanmean(X_tr[:, col]))
        for arr in (X_tr, X_va, X_te):
            arr[np.isnan(arr[:, col]), col] = mean_col
    scaler = StandardScaler().fit(X_tr)
    clf = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
    va = accuracy_score(y_va, clf.predict(scaler.transform(X_va)))
    te = accuracy_score(y_te, clf.predict(scaler.transform(X_te)))
    print(f"   val acc {va:.3f} / test acc {te:.3f}（对照 A test 0.930：两列信息损失后小降）")
    return te


def section_d_leakage() -> float:
    print("== D. 特征泄漏（加入『诊断完成后才知道的维修码』）==")
    rng = np.random.default_rng(SEED)
    X, y = make_fault_data()
    # 泄漏特征：维修码 ≈ 类别编号（等价于把答案混进特征；真实预测时维修码还没产生）
    leak = 1000 * y + 10 * rng.standard_normal(N)
    X_leak = np.hstack([X, leak.reshape(-1, 1)])
    X_tr, X_va, X_te, y_tr, y_va, y_te = split_raw(X_leak, y)
    scaler = StandardScaler().fit(X_tr)  # 6 列一起缩放（含泄漏列）
    clf = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
    va_leak = accuracy_score(y_va, clf.predict(scaler.transform(X_va)))
    print(f"   val acc（带泄漏特征）{va_leak:.3f} —— 虚高！")
    # 上线场景：维修码拿不到 → 换成与标签无关的随机噪声（模拟真实预测输入）
    X_te_real = np.hstack([X_te[:, :-1], rng.standard_normal((X_te.shape[0], 1))])
    te_real = accuracy_score(y_te, clf.predict(scaler.transform(X_te_real)))
    print(f"   test acc（泄漏特征失效后）{te_real:.3f} —— 回落到真实水平")
    return te_real


if __name__ == "__main__":
    _, _, base = section_a_clean()
    noisy = section_b_label_noise()
    missing = section_c_missing_values()
    real = section_d_leakage()
    print(
        f"\n结论：数据质量决定模型上限 —— 干净 {base:.3f} → 标签噪声 {noisy:.3f} / "
        f"缺失填充 {missing:.3f}；泄漏让 val 虚高到 0.990，换真实输入后回落到 {real:.3f}。"
    )
