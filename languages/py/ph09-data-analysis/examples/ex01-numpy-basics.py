# examples/ex01-numpy-basics.py —— NumPy 数组基础：构造 / 形状 / 索引 / 广播 / 向量化
# 验证环境：Python 3.13.9，numpy 2.3.5
# 运行：python3 ex01-numpy-basics.py（离线可跑，已验证）
import numpy as np


def main() -> None:
    # 1. 从列表构造一维数组；向量化：整数组运算，无 for 循环
    arr = np.array([1, 2, 3, 4, 5])
    print("arr:", arr)
    print("arr + 10:", arr + 10)
    print("arr * 2:", arr * 2)
    print("mean:", np.mean(arr), " std:", round(np.std(arr), 4))

    # 2. 形状与 dtype：reshape 重排，shape/dtype 描述数组
    m = np.arange(12).reshape(3, 4)  # 0..11 排成 3 行 4 列
    print("m.shape:", m.shape, " m.dtype:", m.dtype)
    print("m[1, 2]:", m[1, 2])  # 第 2 行第 3 列的元素 = 6
    print("m[:, 1]:", m[:, 1])  # 第 2 列整列切片 = [1 5 9]

    # 3. 广播：形状 (3,1) 与 (3,) 从右往左对齐，扩展成 (3,3)，不复制数据
    a = np.array([[1], [2], [3]])  # 形状 (3,1)
    b = np.array([10, 20, 30])  # 形状 (3,)
    print("broadcast a + b:\n", a + b)

    # 4. 随机数构造器 + 向量化统计（默认随机源，可复现）
    rng = np.random.default_rng(42)
    x = rng.normal(70, 10, 1000)  # 均值 70、标准差 10 的 1000 个样本
    print("normal(70,10,1000): mean =", round(x.mean(), 2), ", std =", round(x.std(), 2))


if __name__ == "__main__":
    main()
