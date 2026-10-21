# 参考解：第 1 题（说清）

1. 路径长度 `h(x)` 越短，`s(x)=2^{−E[h]/c(ψ)}` 越大，越异常。
2. `lrd(x)=1/mean(可达距离)`；`LOF=mean(lrd(邻居))/lrd(x)`，大于 1 表示比邻居稀疏。
3. KDE 的 `p̂(x)` 越大越正常，所以用 `−log p̂(x)` 当异常分数，统一成"越大越异常"。
4. 阈值 `τ=quantile(训练分数, 1−contamination)`；contamination 越大，τ 越低、报警越多。
