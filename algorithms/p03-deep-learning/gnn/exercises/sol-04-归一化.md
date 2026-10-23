# 参考解：归一化

`A_hat=(A+I); d=A_hat.sum(1); A_hat*=d**-0.5[:,None]*d**-0.5[None,:]`
