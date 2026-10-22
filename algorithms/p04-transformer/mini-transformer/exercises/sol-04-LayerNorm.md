# 参考解：第 4 题（实现）——LayerNorm

前向：`mu/var` 沿最后一维，`xhat=(x-mu)/sqrt(var+eps)`，`y=gamma*xhat+beta`。

反向：`dbeta=sum(dy)`，`dgamma=sum(dy*xhat)`，
`dx=(1/std)*(dxhat - mean(dxhat) - xhat*mean(dxhat*xhat))`。

用有限差分检查 `gamma/beta`，误差应 <1e-5。
