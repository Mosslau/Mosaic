# ph21 数据平台 / 数据中心后端 Java 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与 roadmap「21. 数据平台 / 数据中心后端方向 Java 阶段」练习小节的对应**：四题一一对应 roadmap 列出的四个练习——练习 1 = 数据源数据上报 API、练习 2 = 节点管理系统、练习 3 = 版本发布升级平台、练习 4 = Kafka 指标消费服务。
> **验证纪律**：四题均为纯 Java 17，用 `/opt/homebrew/opt/openjdk@17/bin/javac|java` 本机实测，验收命令见各题。

| 练习 | 参考实现 | 用到的本阶段机制 | examples 参照 |
|------|---------|------------------|------|
| 1 数据源数据上报 API | sol-01-data-report/ | 上报校验/每个数据源 seq 去重/并发安全（3.2） | ex02/ex03 |
| 2 节点管理系统 | sol-02-node-management/ | 节点集群批量管理/状态查询/终态保护（3.1） | ex01 |
| 3 版本发布升级平台 | sol-03-release-platform/ | 版本库/批次编排/节点状态机/审计（3.6） | ex06 |
| 4 Kafka 指标消费服务 | sol-04-metric-consumer/ | 多分区/消费组/offset/幂等去重/lag（3.3） | ex05 |

## 练习 1：数据源数据上报 API（★★）

**目标**：实现一个可被 HTTP/Netty 网关 handler 调用的上报判定核心，正确处理坏帧、越界帧与乱序帧。
**要求**：
- 输入数据源上报 `(vin, seq, cpuPct, latencyMs, diskTempC)`，返回判定结果（OK / 拒绝 / 重复）
- 校验 sourceId 格式（如 `LSV` 开头、定长）与物理量程（CPU 水位 0~100、延迟 0~220、磁盘温度 -40~150）
- 按「每个数据源 seq 单调」去重：乱序旧帧返回重复，不覆盖新值
- 线程安全：多路网关并发上报同一 sourceId 时既不丢帧也不乱序覆写
- 提供查询「某数据源当前最新上报」的接口
**验收**：两线程对同一 sourceId 各上报 seq=1..1000 的帧，最终 OK 恰 1000 条且最新帧 seq=1000；混入非法 sourceId 与越界 CPU 水位 帧均被拒。参考实现见 `sol-01-data-report/`。

## 练习 2：节点管理系统（★★）

**目标**：写一个内存版节点集群管理系统：批量注册、按状态查询、上下线与退役操作，状态非法迁移必须被拦截。
**要求**：
- 数据源档案含 sourceId、数据源类型、固件版本、状态；状态集合自定（至少在线/离线/版本发布/退役）
- 支持批量注册与「按状态列出数据源」
- `RETIRED` 为终态：退役数据源不可被拉回在线；未注册 sourceId 不可操作
- 线程安全：并发改状态不产生部分更新（提示：档案整体替换比改字段安全）
**验收**：注册 5 台后执行「3 在线 / 1 版本发布/ 1 离线」操作序列，查询计数正确；终态复活与操作不存在 sourceId 均抛出业务异常。参考实现见 `sol-02-node-management/`。

## 练习 3：版本发布升级平台（★★★）

**目标**：做一个含版本库的 版本发布平台：版本只能递进发布，批次绑定已发布版本，批内每个数据源独立状态机并可并发推进。
**要求**：
- 发布版本：禁止版本倒退（新版本必须高于平台当前最高版本）
- 创建批次：引用已发布版本 + 目标 sourceId 列表，初始全部 PENDING
- 按数据源推进：`advance(vin, from, to)`，当前状态与期望不符即抛异常（防重复推进）
- 批次汇总：能查询批内各状态数量；每次迁移写审计日志
- 并发安全：不同批次可在不同线程同时推进
**验收**：发布 1.4.0/2.0.0 后再发布 1.5.0 被拒；批次 A（3 台）与批次 B（1 台）并发推进互不干扰；批次 A 模拟「2 成功 1 失败」，失败数据源能进入回滚态且审计可查。参考实现见 `sol-03-release-platform/`。

## 练习 4：Kafka 指标消费服务（★★★）

**目标**：写一个内存版 Kafka 消费组：多分区 topic 按 sourceId 哈希分区，多个消费者分摊分区并发消费，重复投递靠幂等去重兜底。
**要求**：
- 生产端：消息按 `sourceId.hashCode() % 分区数` 路由（同一数据源同分区、保序）
- 消费端：N 个 worker 分摊 P 个分区（每分区同一时刻只被一个 worker 读），各自维护 nextOffset，处理完一批才推进「已提交 offset」
- 幂等：共享的去重表保证重复投递不二次入库；能统计新增处理数、被拦截的重复数
- 提供 lag 查询（logEndOffset - 已提交 offset）
**验收**：300 个数据源 × 2 条 = 600 条唯一消息中混入 100 条重复投递，2 个 worker 消费后：新增处理 = 600、distinct 键 = 600、重复全部被识别、lag 归零。参考实现见 `sol-04-metric-consumer/`。

## 验证命令（纯 Java，无第三方依赖）

```bash
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
OUT=/tmp/tl21-sol && mkdir -p $OUT
cd sol-01-data-report && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ReportApiDemo && cd ..
cd sol-02-node-management && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT NodesManagerDemo && cd ..
cd sol-03-release-platform && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ReleasePlatformDemo && cd ..
cd sol-04-metric-consumer && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ConsumerGroupDemo && cd ..
```

全部通过后继续到 [`project/`](../project/)：数据平台后台(收官项目)。
