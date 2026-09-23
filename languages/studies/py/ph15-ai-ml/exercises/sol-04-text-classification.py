#!/usr/bin/env python3
# exercises/sol-04-text-classification.py —— 练习 4 参考实现：日志文本三级分类
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 sol-04-text-classification.py（离线可跑，已验证）
# 验证状态：已验证 —— 固定 seed=42，数字可复现；小语料 + 随机模板，换 seed 波动较大（±0.1）
# 验证块数字实测：test acc 0.786 / macro-F1 0.765（14 条测试，混淆矩阵 [[2,2,1],[0,5,0],[0,0,4]]）；
#                误判全部是 info → warning/error（无关键词的 info 句被挤出去）
"""练习 4（文本分类，对应 roadmap）：把日志文本变成向量再分类。

任务：用「句子模板 + 每类专属词表」合成一批设备日志（info / warning / error 三级，
措辞刻意有交集：component、brake、software 在多级都出现），流程：
  文本 → TfidfVectorizer（词频×逆文档频率，把「句子」变「向量」）→
  LogisticRegression → accuracy / macro-F1 / 混淆矩阵评估。
要点：
  1. 文本必须先向量化才能进 sklearn——TF-IDF 让罕见词（往往是关键信息）
     权重更高，常见词（of/the）权重更低；
  2. 测出来的 acc 只有 0.786——不是模型差，是语料措辞有交集且量小：
     「文本分类的天花板同样由数据（语料）质量决定」；
  3. 混淆矩阵的读法：info 被误判成 warning/error 或反之，往往是句子同时含
     两级的关键词（如 brake check passed 里的 brake）。
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

SEED = 42
N_PER_CLASS = 15

# 每级日志的「句子模板 + 可填词表」：故意让 component/brake/software 等词跨级出现
TEMPLATES: dict[str, list[tuple[str, list[str]]]] = {
    "info": [
        (
            "{x} started and completed successfully",
            [
                "software update",
                "charging session",
                "self test",
                "brake check",
                "map refresh",
            ],
        ),
        ("all system checks passed, no faults found",),
        (
            "{x} is within normal range",
            ["component temperature", "mount torque", "coolant level"],
        ),
        ("telemetry connection restored, data flowing again",),
        ("route to destination recalculated",),
        ("{x} reached target level", ["charge level", "cabin temperature"]),
    ],
    "warning": [
        ("{x} is low, please recharge", ["component", "washer fluid"]),
        (
            "{x} pressure low on {y}",
            ["tire"],
            ["front left", "front right", "rear left", "rear right"],
        ),
        ("charging speed reduced due to high {x}", ["temperature", "load"]),
        ("signal weak, telemetry {x}", ["delayed", "intermittent"]),
        ("{x} approaching limit, schedule service", ["brake pads", "tire tread"]),
        (
            "software update paused, {x} below threshold",
            ["component level", "network signal"],
        ),
    ],
    "error": [
        (
            "{x} fault detected, device disabled",
            ["motor inverter", "charger", "brake module"],
        ),
        (
            "communication lost with {x}",
            ["component management system", "sensor cluster", "charger"],
        ),
        ("{x} failed, rolling back", ["software update", "thermal management"]),
        ("high voltage {x} stuck", ["contactor", "relay"]),
        ("{x} pressure lost", ["brake hydraulic", "coolant"]),
        ("component {x} critical", ["temperature", "cell imbalance"]),
    ],
}


def make_logs(cls: str, n: int, seed: int) -> list[str]:
    """按类别的模板 + 词表合成 n 条日志（措辞自然、词表跨级重叠）。"""
    rng = np.random.default_rng(seed)
    outs: list[str] = []
    for _ in range(n):
        tmpl, *fills = TEMPLATES[cls][int(rng.integers(0, len(TEMPLATES[cls])))]
        values = dict(zip("xyzw", (str(rng.choice(pool)) for pool in fills)))
        outs.append(tmpl.format(**values))
    return outs


def main() -> None:
    texts = (
        make_logs("info", N_PER_CLASS, SEED)
        + make_logs("warning", N_PER_CLASS, SEED + 1)
        + make_logs("error", N_PER_CLASS, SEED + 2)
    )
    labels = np.array(
        ["info"] * N_PER_CLASS + ["warning"] * N_PER_CLASS + ["error"] * N_PER_CLASS
    )
    X_tr, X_te, y_tr, y_te = train_test_split(
        texts, labels, test_size=0.3, stratify=labels, random_state=SEED
    )

    vectorizer = TfidfVectorizer(ngram_range=(1, 2))  # 词 + 相邻词对
    Xv_tr = vectorizer.fit_transform(X_tr)  # 只在训练集学词表/IDF
    Xv_te = vectorizer.transform(X_te)
    model = LogisticRegression(max_iter=3000).fit(Xv_tr, y_tr)
    pred = model.predict(Xv_te)

    print(f"== 日志三级分类（训练 {len(X_tr)} / 测试 {len(X_te)}，语料为模板合成）==")
    print(f"   词表大小: {len(vectorizer.vocabulary_)} 个词/词对")
    print(
        f"   test acc {accuracy_score(y_te, pred):.3f} / macro-F1 {f1_score(y_te, pred, average='macro'):.3f}"
    )
    order = ["info", "warning", "error"]
    cm = confusion_matrix(y_te, pred, labels=order)
    print(f"   混淆矩阵（行=真实 / 列=预测）: {cm.tolist()}")
    for t, true, p in zip(X_te, y_te, pred, strict=True):
        if true != p:
            print(f"   误判示例: [{true}] → [{p}] ｜ {t}")

    acc = accuracy_score(y_te, pred)
    assert acc >= 0.7, "测试准确率应 ≥ 0.7（三类随机猜只有 0.33）"
    assert f1_score(y_te, pred, average="macro") >= 0.65
    print("\n验收通过：会走「文本 → 向量 → 模型 → 评估」闭环，能从混淆矩阵解释误判")


if __name__ == "__main__":
    main()
