# examples —— AI 平台 / 训练与推理调度方向阶段完整示例

> 每个示例对应主文档 `22-ai-platform.md` 相关小节（3.1~3.8）的完整可运行版。全部**纯 Java 17 标准库、零第三方依赖、默认包**，数据在代码内确定性自造，可离线复现。运行方式统一为「`javac` 编译到 /tmp + `java` 跑 Demo」，产物不落仓库。

| 文件（目录） | 说明（对应主文档小节） | 验证命令（进入各自目录） | 实测 |
|------|------|------------|------|
| `ex01-training-job/` | 训练任务聚合根与状态机：幂等提交、非法迁移拒绝、重试上限、审计轨迹（3.1） | `javac -encoding UTF-8 -d /tmp/ph22-ex01 *.java && java -cp /tmp/ph22-ex01 TrainingJobDemo` | **7/7 PASS** |
| `ex02-gpu-pool/` | GPU 资源台账：分配/回收、不变量 `allocated+free==total`、租户占用（3.2） | `javac -encoding UTF-8 -d /tmp/ph22-ex02 *.java && java -cp /tmp/ph22-ex02 GpuPoolDemo` | **10/10 PASS** |
| `ex03-scheduler/` | 三种调度策略对比：FIFO / 优先级 / 回填，同输入决策确定（3.3 / 4.1） | `javac -encoding UTF-8 -d /tmp/ph22-ex03 *.java && java -cp /tmp/ph22-ex03 SchedulerDemo` | **9/9 PASS** |
| `ex04-model-registry/` | 模型注册表：语义化版本比较、血缘校验、晋级门槛、禁止倒退（3.4） | `javac -encoding UTF-8 -d /tmp/ph22-ex04 *.java && java -cp /tmp/ph22-ex04 ModelRegistryDemo` | **8/8 PASS** |
| `ex05-inference-rollout/` | 推理服务生命周期：控制器循环收敛、滚动更新、灰度切流、失败回滚（3.5 / 4.2 / 4.3） | `javac -encoding UTF-8 -d /tmp/ph22-ex05 *.java && java -cp /tmp/ph22-ex05 RolloutDemo` | **7/7 PASS** |
| `ex06-data-versioning/` | 数据集/特征版本台账：校验和、快照一致性、训练-推理版本一致性（3.6） | `javac -encoding UTF-8 -d /tmp/ph22-ex06 *.java && java -cp /tmp/ph22-ex06 DataVersionDemo` | **8/8 PASS** |
| `ex07-quota-metering/` | 多租户配额（拒绝而非排队）+ 事件驱动 GPU 秒计量（3.7 / 4.4） | `javac -encoding UTF-8 -d /tmp/ph22-ex07 *.java && java -cp /tmp/ph22-ex07 QuotaMeteringDemo` | **9/9 PASS** |
| `ex08-ai-ops-console/` | 运维一屏（队列/算力/版本/服务）+ Prometheus 文本指标（3.8） | `javac -encoding UTF-8 -d /tmp/ph22-ex08 *.java && java -cp /tmp/ph22-ex08 AiOpsDemo` | **7/7 PASS** |

## 验证说明

- **验证环境**：OpenJDK 17.0.18（Homebrew），无第三方依赖、无外部数据文件；每个 Demo 末尾打印 `ALL PASS: N/N`，出现 FAIL 时以非 0 退出码结束。
- **验证状态：已验证**（本机实测）：8 个示例全部 `javac` 编译通过 + `java` 运行全绿（断言数见上表，合计 65 项）；每份源码文件头的「验证状态」行与上表一致。
- **确定性**：所有示例不读系统时间、不读外部文件；调度策略是纯函数，同一输入重复运行结果逐字节一致（ex03 显式断言两次决策相同）。
- **产物纪律**：编译产物一律写 `/tmp/ph22-exNN`，仓库内不落 `.class`。
- **一处刻意简化（ex03）**：回填需要「队头还要等多久」。示例用**运行中任务剩余分钟数的最大值**作为保守上界（真实平台做可用性预测或分位数估计）；这样策略保持纯函数、决策可重放——见主文档 4.1 与 `BackfillPolicy` 注释。

## 与主文档的差异（如实标注）

| 位置 | 主文档写的是 | 代码实际是 | 原因 |
|------|------------|-----------|------|
| 3.3 `Policy.select` 签名 | `select(queue, freeGpus, tenantUsed)` 三参数 | `select(queue, freeGpus, now, running, remainingMin)` | 回填必须有「运行中任务及其剩余时长」才能估算等待窗口；`now` 显式传入让时间也成为输入（纯函数可重放） |
| 3.5 灰度期 `Status.updated` | 未定义 | 「相对**当前期望版本**的副本数」 | 回滚时期望改回旧版本，`updated` 重新从 0 观测才不会出现「已经更新完了」的误判 |
| 3.6 数据集版本号 | 未规定格式 | `v1/v2/v3` 且按**数值**比较（不是字符串） | 字符串比较会让 `v10 < v9`，与语义化版本纪律冲突 |
