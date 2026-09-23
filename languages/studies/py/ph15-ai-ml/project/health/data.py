"""部件老化数据合成（project/health/data.py）。

生成 N 台设备/部件组的「工作工况 → 健康状态」数据：
- 特征（工况，全部在体检之前就知道）：
    cycles      累计充放电循环次数（次）
    avg_temp    平均工作温度（°C）
    depth       平均放电深度 DoD（%）
    c_rate      平均充电倍率 C（1C=1 小时充满）
- 目标 1：health —— 健康状态（%）。HEALTH = 100 − 循环数 × 每循环老化率 + 噪声，
  每循环老化率 = 基础 0.008 + 高温/深放/大倍率分段加成 + 电芯个体差异。
- 目标 2：grade —— 健康等级（0=健康 HEALTH≥90 / 1=退化 80≤HEALTH<90 / 2=临界 HEALTH<80），
  由带测量误差的 HEALTH 分箱得到（体检本身有噪声）。

⚠️ 数据泄漏教学点：health 是「要预测的目标」，绝不能当特征喂给模型——本数据集
的特征只有工况。真实场景里 HEALTH 靠定期体检实测，模型预测的是两次体检之间的
HEALTH 轨迹（本项目的简化只预测给定工况下的当前 HEALTH）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FEATURES = ["cycles", "avg_temp", "depth", "c_rate"]
GRADE_NAMES = ["健康", "退化", "临界"]

# 分箱阈值：HEALTH ≥90 健康 / ≥80 退化 / <80 临界
GRADE_EDGES = (90.0, 80.0)


@dataclass
class ComponentDataset:
    """一份可划分的部件老化数据。X 为 (n, 4) 工况矩阵，health/grade 为目标。"""

    X: np.ndarray
    health: np.ndarray
    grade: np.ndarray

    def split(self, test_size: float, seed: int) -> tuple[ComponentDataset, ComponentDataset]:
        """按等级分层划分 train/test（sklearn 的 train_test_split 需要导入）。"""
        from sklearn.model_selection import train_test_split

        X_tr, X_te, s_tr, s_te, g_tr, g_te = train_test_split(
            self.X,
            self.health,
            self.grade,
            test_size=test_size,
            stratify=self.grade,
            random_state=seed,
        )
        return ComponentDataset(X_tr, s_tr, g_tr), ComponentDataset(X_te, s_te, g_te)


def _aging_loss(
    avg_temp: np.ndarray, depth: np.ndarray, c_rate: np.ndarray, cell_noise: np.ndarray
) -> np.ndarray:
    """每循环老化率（%/cycle）：基础 + 高温/深放/大倍率的分段加成 + 电芯差异。"""
    return (
        0.008
        + 0.00025 * np.maximum(avg_temp - 25, 0)  # 高温加速老化（25°C 为基准）
        + 0.0005 * np.maximum(depth - 70, 0)  # 深放（>70% DoD）加速老化
        + 0.0015 * np.maximum(c_rate - 1.5, 0)  # 大倍率充电加速老化
        + cell_noise
    )


def make_component_data(n: int, seed: int) -> ComponentDataset:
    """合成 n 组部件数据。seed 固定 → 完全可复现。"""
    rng = np.random.default_rng(seed)
    cycles = rng.uniform(100, 3200, n)  # 累计循环次数
    avg_temp = rng.uniform(18, 45, n)  # 平均温度
    depth = rng.uniform(40, 100, n)  # 平均放电深度
    c_rate = rng.uniform(0.3, 2.2, n)  # 平均充电倍率
    X = np.column_stack([cycles, avg_temp, depth, c_rate])

    loss = _aging_loss(avg_temp, depth, c_rate, rng.normal(0, 0.0012, n))
    health_raw = 100 - cycles * loss  # 纯老化轨迹（无噪声）
    health = np.clip(health_raw + rng.normal(0, 1.2, n), 40, 100)  # 体检噪声
    noisy = health_raw + rng.normal(0, 1.5, n)  # 等级标签含更大测量误差
    grade = np.where(noisy >= GRADE_EDGES[0], 0, np.where(noisy >= GRADE_EDGES[1], 1, 2)).astype(
        int
    )

    order = rng.permutation(n)
    return ComponentDataset(X[order], health[order], grade[order])


def load_component_data(n: int = 1500, seed: int = 42) -> ComponentDataset:
    """默认数据入口（demo/训练共用，n 小则跑得快）。"""
    return make_component_data(n, seed)
