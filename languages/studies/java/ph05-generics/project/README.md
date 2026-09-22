# ph05 阶段项目：泛型缓存容器（TtlCache）

## 需求

对应 Roadmap「ph05 泛型阶段」推荐项目第一个「泛型缓存容器」（第二个「泛型分页结果」暂不做）。主文档第 5 章场景表将「泛型工具类（容器/缓存）」指向泛型类 `<T>`，本项目落地这一模式：实现一个**泛型 TTL（Time-To-Live，生存时间）缓存容器**，`put` 时记录过期时刻，`get` 命中未过期条目返回值、命中已过期条目则**惰性删除**并返回 `null`，另提供 `purgeExpired()` 批量清理过期条目。选 TTL 而非 LRU——ph04 阶段项目已做过 LRU Cache，TTL 体现不同的淘汰语义（按时间而非按访问频次），且本项目不依赖 `LinkedHashMap` 钩子，核心逻辑自实现，更能检验对泛型类与集合的掌握。

项目以「设备状态缓存」为场景（deviceId → 状态字符串），核心类 `TtlCache` 与场景无关，可复用于会话缓存、配置缓存、验证码缓存等任何 `K/V` 键值。

## 功能清单

- [ ] 泛型缓存 `TtlCache<K, V>`，`put(K key, V value, long ttlMillis)` 写入并记录过期时刻（`ttlMillis <= 0` 抛 `IllegalArgumentException`）
- [ ] `get(K key)`：命中未过期返回值；命中已过期惰性删除并返回 `null`；不存在返回 `null`
- [ ] 同 key 重复 `put` 覆盖 value 并**重新计时**（刷新 TTL）
- [ ] `remove(K key)` 立即删除；`containsKey` 感知过期（过期视为不存在）
- [ ] `purgeExpired()` 批量清理过期条目，返回清理数量；`size()` / `isEmpty()` / `clear()`
- [ ] 时间源用 `System.nanoTime()`（单调递增，不受系统时钟调整影响）
- [ ] 自测入口 `TtlCacheApp`，覆盖七条路径：基础命中、TTL 过期、覆盖刷新、remove/containsKey/clear、purgeExpired、Integer 泛型、非法 TTL 校验

## 验收标准

- `javac ttl-cache.java ttl-cache-app.java` 编译零错误
- `java TtlCacheApp` 全部自测通过，末尾打印「全部自测通过」
- TTL 80ms 的条目：未过期时 `get` 命中，`Thread.sleep(200)` 后 `get` 返回 `null` 且 `size()` 已减一（惰性删除生效）
- 同 key 覆盖后 TTL 重新计时：覆盖后 120ms 内命中，超过后过期
- `purgeExpired()` 能一次清理全部过期条目并返回正确数量
- 自测失败时抛 `AssertionError` 并给出失败路径名（不静默）

## 扩展方向

- **淘汰策略替换**：把过期判定抽成接口（`EvictionPolicy`），在 TTL 之外再实现 LRU/容量上限策略——复用泛型容器的 K/V 骨架
- **手写哈希实现**：不用 `HashMap`，用数组 + 链表手写一遍——深化主文档第 4 章「哈希桶」心智（为 analysis/ 积累素材）
- **后台清扫线程**：惰性删除之外，起定时线程周期性 `purgeExpired()`，防止长期不访问的过期条目堆积——线程与并发属后续阶段
- **统计指标**：记录命中数、miss 数、清理数，计算命中率——为「缓存与高并发阶段」的指标化缓存设计预热
- **值缺省语义**：`getOrDefault(key, fallback)`，参考 `Optional.orElse` 的泛型用法（练习 1 的 `getOrElse` 思路）

## 验证环境

- 工具链：jenv OpenJDK 17.0.16
- 编译：`javac ttl-cache.java ttl-cache-app.java`
- 运行：`java TtlCacheApp`

```bash
# 1. 编译
javac ttl-cache.java ttl-cache-app.java
# 2. 运行自测
java TtlCacheApp
```

已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，自测全部通过）。
