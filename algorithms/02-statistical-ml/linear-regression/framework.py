"""线性回归与梯度下降 — 框架对照调用

用手写实现同样的数据和指标，调 sklearn / PyTorch 现成接口跑一遍。
目的：
1. 验证手写实现的正确性（指标应对齐）
2. 感受框架封装的便利与隐藏的细节
3. 记录框架内部额外做的优化（写回 README「框架对照」一节）
"""


def run_framework(X_train, X_test, y_train, y_test):
    """用框架接口完成训练 + 预测，返回与手写版对齐的指标字典。"""
    # TODO: 例：from sklearn.linear_model import LinearRegression
    raise NotImplementedError("TODO: 调框架接口，返回 {'metric': ..., 'time_sec': ...}")


if __name__ == "__main__":
    raise SystemExit("请先完成 run_framework，由 demo.py 统一调用对比")
