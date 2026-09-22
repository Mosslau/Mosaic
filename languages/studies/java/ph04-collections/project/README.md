# ph04 阶段项目：LRU Cache

## 需求

对应 Roadmap「ph04 集合框架阶段」推荐项目第一个「LRU Cache」（第二个「设备状态表」暂不做）。主文档第 5 章场景表将「LRU 缓存」指向 `LinkedHashMap（accessOrder=true）`，本项目落地这一模式：实现一个**泛型 LRU（Least Recently Used，最近最少使用）缓存**，容量可配置，容量满时自动淘汰最久未访问的条目。核心机制是 `LinkedHashMap` 的两个钩子——构造参数 `accessOrder=true`（每次 `get`/`put` 命中把条目移到内部链表末尾，链表头即最久未访问）与 `removeEldestEntry`（每次 `put` 后检查，超容量即淘汰链表头）。项目以「设备状态缓存」为场景（deviceId → 状态字符串），核心类 `LruCache` 与场景无关、可复用于任何 `K/V` 键值。

## 功能清单

- [ ] 泛型缓存 `LruCache<K, V>`，容量构造时指定（`capacity <= 0` 抛 `IllegalArgumentException`）
- [ ] 继承 `LinkedHashMap`，构造时 `accessOrder=true`——`get`/`put` 命中会把条目移到链表末尾（最新）
- [ ] 重写 `removeEldestEntry`——`size() > capacity` 时淘汰链表头（最久未访问条目）
- [ ] `put` 已有 key 覆盖 value，不新增条目、不触发淘汰
- [ ] `get` 不存在的 key 返回 `null`
- [ ] 自测入口 `LruCacheApp`，覆盖四条路径：命中刷新、LRU 淘汰顺序、覆盖不涨容量、miss 返回 null（外加非法容量校验）

## 验收标准

- `javac LruCache.java LruCacheApp.java` 编译零错误
- `java LruCacheApp` 全部自测通过，末尾打印「全部自测通过」
- 容量 3 时依次 `put(A/B/C)`，`get(A)` 后再 `put(D)` → 淘汰的恰是 `B`（最久未用），剩余顺序 `[C, A, D]`
- 继续 `put(E)` → 淘汰 `C`，剩余顺序 `[A, D, E]`
- 自测失败时抛 `AssertionError` 并给出失败路径名（不静默）

## 扩展方向

- **手写实现**：不用 `LinkedHashMap`，用 `HashMap` + 双向链表手写一遍——深化主文档第 4 章的哈希桶与链表心智（为 analysis/ 积累素材）
- **线程安全**：对 `get`/`put` 加锁或用 `ConcurrentHashMap` 自实现——并发与线程安全主题属后续阶段
- **缓存指标**：统计命中率、淘汰次数、访问总数，用 `get` 时自己计数
- **容量策略**：支持 `capacity <= 0` 之外的淘汰回调（如淘汰时打印日志），重写 `removeEldestEntry` 时把被淘汰 key 暴露出去

## 验证环境

- 工具链：jenv OpenJDK 17.0.16
- 编译：`javac LruCache.java LruCacheApp.java`
- 运行：`java LruCacheApp`

```bash
# 1. 编译
javac LruCache.java LruCacheApp.java
# 2. 运行自测
java LruCacheApp
```

已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，自测全部通过）。
