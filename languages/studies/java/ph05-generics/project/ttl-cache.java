// project/ttl-cache.java —— 泛型 TTL 缓存容器：put 时记录过期时间，get 命中返回、过期惰性删除
// 核心类，与场景无关，可复用于任何 K/V 键值对（设备状态、会话、配置等）
// 验证环境：OpenJDK 17.0.16
// 编译：javac ttl-cache.java ttl-cache-app.java
// 运行：java TtlCacheApp
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

// 泛型 TTL（Time-To-Live，生存时间）缓存容器
// 设计要点：
// - 时间源用 System.nanoTime()——单调递增，不受系统时钟调整影响（currentTimeMillis 会被校时跳变污染）
// - 过期采用「惰性删除」：get/containsKey 命中过期条目时删除，不额外起线程清扫
// - size() 统计的是存储条目数，含已过期未清理的条目；purgeExpired() 显式批量清理
class TtlCache<K, V> {
    // 值 + 绝对过期时刻（纳秒）；用静态内部类持有过期时间，Map 只存一份引用
    private static final class Entry<V> {
        final V value;
        final long expiresAtNanos;

        Entry(V value, long expiresAtNanos) {
            this.value = value;
            this.expiresAtNanos = expiresAtNanos;
        }
    }

    private final Map<K, Entry<V>> store = new HashMap<>();

    // 写入：ttlMillis 为生存时间（毫秒）；同 key 重复 put 覆盖值并重新计时
    public void put(K key, V value, long ttlMillis) {
        if (ttlMillis <= 0) throw new IllegalArgumentException("ttlMillis 必须 > 0");
        long expiresAt = System.nanoTime() + ttlMillis * 1_000_000L;
        store.put(key, new Entry<>(value, expiresAt));
    }

    // 读取：命中且未过期返回值；过期则惰性删除并返回 null；不存在返回 null
    public V get(K key) {
        Entry<V> e = store.get(key);
        if (e == null) return null;
        if (System.nanoTime() > e.expiresAtNanos) {
            store.remove(key);   // 惰性过期：查到才删
            return null;
        }
        return e.value;
    }

    // 立即删除（不过问是否过期），返回被删值，不存在返回 null
    public V remove(K key) {
        Entry<V> e = store.remove(key);
        return e == null ? null : e.value;
    }

    // 批量清理所有过期条目，返回清理数量
    public int purgeExpired() {
        int removed = 0;
        long now = System.nanoTime();
        Iterator<Map.Entry<K, Entry<V>>> it = store.entrySet().iterator();
        while (it.hasNext()) {
            if (now > it.next().getValue().expiresAtNanos) {
                it.remove();
                removed++;
            }
        }
        return removed;
    }

    public boolean containsKey(K key) { return get(key) != null; }
    public int size() { return store.size(); }        // 含已过期未清理的条目
    public boolean isEmpty() { return store.isEmpty(); }
    public void clear() { store.clear(); }
}
