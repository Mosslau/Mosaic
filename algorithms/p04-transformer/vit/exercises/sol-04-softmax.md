# 参考解：softmax 反向

`dS=P*(dP - (dP*P).sum(-1,keepdims=True))`。
