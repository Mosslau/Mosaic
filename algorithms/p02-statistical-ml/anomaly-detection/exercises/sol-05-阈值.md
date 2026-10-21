# 参考解：第 5 题（迁移）——阈值与 F1

在 digits one-class 数据上训练 IF，扫 contamination，算测试精确率/召回率/F1。

**预期**：contamination 较小时精确率高、召回低；较大时反过来。F1 在中间某点最好。
AUC 与阈值无关，所以"模型排序好"不等于"当前阈值好用"。
