"""数据合成测试：形状、范围、可复现性、等级分布合理性。"""

from __future__ import annotations

import numpy as np

from bhealth.data import FEATURES, load_battery_data


def test_shape_and_columns():
    """X 是 (n, 4)，特征与 FEATURES 对应，目标是一维数组。"""
    data = load_battery_data(n=300, seed=1)
    assert data.X.shape == (300, 4)
    assert data.soh.shape == (300,)
    assert data.grade.shape == (300,)
    assert data.X.shape[1] == len(FEATURES)


def test_value_ranges_plausible():
    """SOH 应在 [40, 100]，等级在 {0, 1, 2}，工况为正。"""
    data = load_battery_data(n=500, seed=2)
    assert data.soh.min() >= 40 and data.soh.max() <= 100
    assert set(np.unique(data.grade)).issubset({0, 1, 2})
    assert (data.X > 0).all()


def test_deterministic_same_seed():
    """同 seed 完全可复现（训练可复现的地基）。"""
    a = load_battery_data(n=400, seed=7)
    b = load_battery_data(n=400, seed=7)
    assert np.array_equal(a.X, b.X)
    assert np.array_equal(a.soh, b.soh)
    assert np.array_equal(a.grade, b.grade)


def test_split_is_stratified_and_disjoint():
    """train/test 划分按等级分层且索引无交集。"""
    data = load_battery_data(n=600, seed=3)
    train, test = data.split(test_size=0.25, seed=42)
    assert train.X.shape[0] == 450 and test.X.shape[0] == 150
    tr_keys = {tuple(r) for r in train.X.tolist()}
    te_keys = {tuple(r) for r in test.X.tolist()}
    assert tr_keys.isdisjoint(te_keys), "train/test 不允许有同一行样本"
    tr_dist = np.bincount(train.grade, minlength=3) / len(train.grade)
    te_dist = np.bincount(test.grade, minlength=3) / len(test.grade)
    assert np.abs(tr_dist - te_dist).max() < 0.05, "分层抽样应保持等级比例"


def test_aging_is_physically_monotone():
    """老化方向 sanity：相同工况下，循环数更多 → SOH 更低（骨架逻辑）。"""
    data = load_battery_data(n=2000, seed=5)
    low = data.X[:, 0] < 500
    high = data.X[:, 0] > 2500
    assert data.soh[low].mean() > data.soh[high].mean() + 5, "循环越多 SOH 应越低"
