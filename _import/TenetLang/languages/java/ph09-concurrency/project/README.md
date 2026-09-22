# ph09 阶段项目：线程池任务调度器

## 需求

对应 Roadmap「ph09 多线程与并发阶段」推荐项目第一个「线程池任务调度器」：手动配置 `ThreadPoolExecutor`（核心/最大/有界队列/拒绝策略），提交带优先级的任务，验证「先填队列后扩线程」的提交流程与拒绝策略告警，统计执行耗时，最后优雅关闭。项目覆盖本阶段核心知识点：线程池参数与提交流程（3.2 / 4.3）、有界队列防 OOM（3.2）、优先级调度（PriorityBlockingQueue + Comparable）、自定义线程工厂、自定义 `RejectedExecutionHandler`（拒绝不静默）、`volatile` 可见性（3.3）、`shutdown`/`awaitTermination` 优雅关闭。

## 文件结构

| 文件 | 类 | 职责 |
|------|----|------|
| task-scheduler.java | TaskScheduler | 线程池构建 + 提交 20 个任务 + 优先级调度 + 拒绝告警 + 统计 + 自测断言 |
| （内含） | TaskScheduler.Task | 任务：id + 优先级 + 提交序号，实现 `Comparable` 决定出队顺序 |
| （内含） | TaskScheduler.BoundedPriorityQueue | 有界优先级队列：`PriorityBlockingQueue` 子类，`offer` 超容量返回 false |

## 功能清单

- [ ] 有界优先级队列：`BoundedPriorityQueue extends PriorityBlockingQueue`，容量满时 `offer` 返回 false——修复无界队列 OOM 隐患，同时保留优先级出队语义
- [ ] 优先级调度：队列按（优先级升序、提交序号升序）出队，任务按优先级顺序启动
- [ ] 自定义线程工厂：线程统一命名 `scheduler-worker-N`
- [ ] 自定义拒绝策略：打印告警日志（含 poolSize/queueSize）并计数，不静默丢弃
- [ ] 提交流程验证：core=2 / max=4 / 队列容量 6，提交 20 个阻塞任务 → 接受 10（2 核心 + 6 队列 + 2 扩线程）、拒绝 10
- [ ] 执行耗时统计：avg / max（业务耗时 20ms，统计约 20ms 级）
- [ ] 优雅关闭：`shutdown` + `awaitTermination`，超时兜底 `shutdownNow`
- [ ] 自测 main：无参数运行，断言失败抛 `AssertionError`，通过打印「全部自测通过」

## 验收标准

- `javac task-scheduler.java` 编译零错误
- `java TaskScheduler` 全部自测通过，末尾打印「全部自测通过」；运行无 `.class`/日志残留仓库内
- 自测覆盖：接受数 10 / 拒绝数 10；被拒绝 id 恰为 11~20；前 4 个启动的任务优先级全为 1（占核心/扩线程的 id 1,2,9,10）；队列中 6 个任务按优先级 `[2,2,3,3,4,4]` 顺序启动；工作线程名统一 `scheduler-worker-N`；优雅关闭成功
- 源码中无无界队列直接当 `workQueue`、无静默丢弃任务的拒绝策略

## 扩展方向

- **并发文件处理工具**：Roadmap 推荐项目第二个——多线程扫描目录、并发读取文件做词频统计，用 CompletableFuture 编排并汇总到 ConcurrentHashMap（示例 4 / 示例 5 已给出核心句式）；进阶用虚拟线程跑 IO 密集的文件读取对比性能（示例 6）
- **定时任务**：用 `ScheduledExecutorService` 支持 `schedule`/`scheduleAtFixedRate`（主文档 5. 使用场景表）
- **优先级队列容量不足的权衡**：本项目用有界优先队列牺牲了「永不拒绝」，生产可改用每优先级一队列的环形调度（按优先级加权取队），避免低优先级任务长期饿死
- **观察者接入**：拒绝告警改为回调/指标上报，衔接 ph12 工程质量阶段的可观测性

## 验证环境

- 工具链：OpenJDK 17.0.18（Homebrew，`javac -version` → 17.0.18）
- 编译：`javac task-scheduler.java`
- 运行：`java TaskScheduler`

```bash
# 1. 编译
javac task-scheduler.java
# 2. 运行自测
java TaskScheduler
# 3. 验证后清理 .class
rm -f *.class
```

已在本环境用 OpenJDK 17.0.18 编译运行验证（零错误，自测全部通过）。
