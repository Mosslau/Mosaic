#!/usr/bin/env python3
# examples/ex02-feature-engineering.py —— 特征工程：缩放与类别编码（主文档 3.4）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 ex02-feature-engineering.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定 seed=42 下的本机实测，完全可复现；
#           换 seed 或数据划分会波动（约 ±1~2 个百分点），对比方向稳定
# 验证块数字实测：kNN 未缩放 test 0.890 → 缩放后 0.930；RF 缩放前后完全一致 0.947；
#                LR 类别 label-encoding test 0.917 → one-hot 0.927（batch C 0.896→0.925）
"""特征工程演示：同样的数据，特征怎么「喂」给模型，结果不同。

  A. 量纲与缩放：五列量纲差异巨大（temp≈40、voltage≈0.3），未缩放时欧氏距离
     被大数域列支配，kNN 等于「只看 temp」→ 缩放后五列同权重，test 从 0.890
     升到 0.930；树模型按阈值分裂、对单调缩放天然不敏感，RF 前后完全一致。
  B. 类别编码：电芯批次（A/B/C/D）是名义类别；label-encoding 把 0..3 当连续值，
     隐式假设「A<B<C<D 的顺序」——B/D 批次电压都偏高（非单调），单系数拟合不了；
     one-hot 每类一个哑变量、无顺序假设 → test 0.917 升到 0.927。
结论：特征工程是建模决策，不是清洗步骤——「喂什么形状」由模型的距离/分裂/
线性假设决定，先想模型再定编码与缩放。
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
N = 1500
# 类别 0=健康 88%、1=充电过压 8%、2=过热振动 4%
CATS = ["A", "B", "C", "D"]


def make_fault_data(seed: int = SEED, batch_off: dict[str, float] | None = None) -> tuple:
    """生成部件传感器故障数据；batch_off 非空时追加名义类别「电芯批次」及其电压偏移。

    数据与批次必须来自同一个随机流（同一个 rng），保证复现与划分稳定。
    返回 (X, y) 或 (X, y, batch)。
    """
    rng = np.random.default_rng(seed)
    n0, n1 = int(N * 0.88), int(N * 0.08)
    n2 = N - n0 - n1

    def gauss(mean: list[float], std: list[float], k: int) -> np.ndarray:
        return np.asarray(mean) + np.asarray(std) * rng.standard_normal((k, 5))

    X = np.vstack(
        [
            gauss([30, 3.7, 10, 0.5, 1.2], [5, 0.16, 2.8, 0.3, 0.12], n0),  # 健康
            gauss([34, 4.0, 8.5, 1.0, 1.4], [5, 0.3, 3.2, 0.4, 0.18], n1),  # 充电过压
            gauss([46, 3.7, 12, 1.6, 1.5], [12, 0.28, 4.5, 1.2, 0.35], n2),  # 过热振动
        ]
    )
    y = np.concatenate([np.zeros(n0), np.ones(n1), np.full(n2, 2)]).astype(int)
    idx = rng.permutation(N)
    X, y = X[idx], y[idx]
    if batch_off is not None:
        batch = np.array([rng.choice(CATS) for _ in range(N)])
        X[:, 1] += np.array([batch_off[b] for b in batch])  # voltage 列叠加批次效应
        return X, y, batch
    return X, y


def split60_20_20(X: np.ndarray, y: np.ndarray, extra: np.ndarray | None = None) -> tuple:
    """60/20/20 划分；extra 为类别标签列（字符串数组）时同步划分。"""
    if extra is None:
        X_tr, X_tmp, y_tr, y_tmp = train_test_split(
            X, y, test_size=0.4, stratify=y, random_state=SEED
        )
        X_va, X_te, y_va, y_te = train_test_split(
            X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=SEED
        )
        return X_tr, X_va, X_te, y_tr, y_va, y_te
    X_tr, X_tmp, y_tr, y_tmp, b_tr, b_tmp = train_test_split(
        X, y, extra, test_size=0.4, stratify=y, random_state=SEED
    )
    X_va, X_te, y_va, y_te, b_va, b_te = train_test_split(
        X_tmp, y_tmp, b_tmp, test_size=0.5, stratify=y_tmp, random_state=SEED
    )
    return X_tr, X_va, X_te, y_tr, y_va, y_te, b_tr, b_va, b_te


def section_a_scaling() -> None:
    print("== A. 量纲与缩放（kNN 是距离模型，树模型不敏感）==")
    X, y = make_fault_data()
    print("   原始列标准差: " + " ".join(f"{v:.3f}" for v in X.std(axis=0)))
    X_tr, X_va, X_te, y_tr, y_va, y_te = split60_20_20(X, y)

    knn_raw = KNeighborsClassifier(n_neighbors=5).fit(X_tr, y_tr)
    print(
        f"   kNN 未缩放: val {accuracy_score(y_va, knn_raw.predict(X_va)):.3f} "
        f"/ test {accuracy_score(y_te, knn_raw.predict(X_te)):.3f}"
    )
    scaler = StandardScaler().fit(X_tr)
    knn_sc = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
    print(
        f"   kNN 缩放后: val {accuracy_score(y_va, knn_sc.predict(scaler.transform(X_va))):.3f} "
        f"/ test {accuracy_score(y_te, knn_sc.predict(scaler.transform(X_te))):.3f}"
    )

    rf_raw = RandomForestClassifier(n_estimators=200, random_state=SEED).fit(X_tr, y_tr)
    rf_sc = RandomForestClassifier(n_estimators=200, random_state=SEED).fit(
        scaler.transform(X_tr), y_tr
    )
    print(
        f"   RF  未缩放: val {accuracy_score(y_va, rf_raw.predict(X_va)):.3f} "
        f"/ test {accuracy_score(y_te, rf_raw.predict(X_te)):.3f}"
    )
    va_rf = accuracy_score(y_va, rf_sc.predict(scaler.transform(X_va)))
    te_rf = accuracy_score(y_te, rf_sc.predict(scaler.transform(X_te)))
    print(f"   RF  缩放后: val {va_rf:.3f} / test {te_rf:.3f}（与未缩放完全一致）")


def section_b_categorical_encoding() -> None:
    print("== B. 类别编码（电芯批次 A/B/C/D，B/D 批次电压偏高 0.30V）==")
    X, y, batch = make_fault_data(seed=SEED, batch_off={"A": 0.0, "B": 0.30, "C": 0.0, "D": 0.30})

    X_tr, X_va, X_te, y_tr, y_va, y_te, b_tr, b_va, b_te = split60_20_20(X, y, batch)
    code_of = np.vectorize(lambda b: CATS.index(b))

    # label-encoding：把 A/B/C/D 当作连续数 0..3（隐式假设存在顺序关系）
    c_tr, c_va, c_te = (code_of(b).reshape(-1, 1) for b in (b_tr, b_va, b_te))
    sc_le = StandardScaler().fit(np.hstack([X_tr, c_tr]))
    lr_le = LogisticRegression(max_iter=3000, random_state=SEED).fit(
        sc_le.transform(np.hstack([X_tr, c_tr])), y_tr
    )
    va_le = accuracy_score(y_va, lr_le.predict(sc_le.transform(np.hstack([X_va, c_va]))))
    te_le = accuracy_score(y_te, lr_le.predict(sc_le.transform(np.hstack([X_te, c_te]))))
    print(f"   LR label-encoding: val {va_le:.3f} / test {te_le:.3f}（把名义类别当顺序数）")

    # one-hot：每类一个哑变量，无顺序假设（sklearn 不自动支持字符串→须手动 OneHotEncoder）
    oh = OneHotEncoder(categories=[CATS], sparse_output=False, handle_unknown="ignore")
    b_tr_o = oh.fit_transform(b_tr.reshape(-1, 1))
    b_va_o = oh.transform(b_va.reshape(-1, 1))
    b_te_o = oh.transform(b_te.reshape(-1, 1))
    sc_oh = StandardScaler().fit(np.hstack([X_tr, b_tr_o]))
    lr_oh = LogisticRegression(max_iter=3000, random_state=SEED).fit(
        sc_oh.transform(np.hstack([X_tr, b_tr_o])), y_tr
    )
    va_oh = accuracy_score(y_va, lr_oh.predict(sc_oh.transform(np.hstack([X_va, b_va_o]))))
    te_oh = accuracy_score(y_te, lr_oh.predict(sc_oh.transform(np.hstack([X_te, b_te_o]))))
    print(f"   LR one-hot:        val {va_oh:.3f} / test {te_oh:.3f}（每类独立系数）")

    # 分批看差异在哪（偏移叠加在 B/D 上，label-encoding 的「顺序假设」在非单调
    # 效应上吃瘪；A/B 无偏移、两种编码几乎一致）
    pred_le = lr_le.predict(sc_le.transform(np.hstack([X_te, c_te])))
    pred_oh = lr_oh.predict(sc_oh.transform(np.hstack([X_te, b_te_o])))
    parts: list[str] = []
    for b in CATS:
        mask = b_te == b
        parts.append(
            f"{b} {accuracy_score(y_te[mask], pred_le[mask]):.3f}→"
            f"{accuracy_score(y_te[mask], pred_oh[mask]):.3f}"
        )
    print("   分批 test acc（label-enc → one-hot）: " + " / ".join(parts))


if __name__ == "__main__":
    section_a_scaling()
    section_b_categorical_encoding()
