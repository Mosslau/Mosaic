/* project/LruCache.java —— LRU Cache 核心类（泛型，继承 LinkedHashMap，accessOrder 模式实现最近最少使用淘汰）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac LruCache.java LruCacheApp.java
 * 运行：java LruCacheApp
 * 验证状态：已验证：OpenJDK 17.0.16
 */
import java.util.LinkedHashMap;
import java.util.Map;

public class LruCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;

    // accessOrder=true：内部双向链表按访问顺序排列，最近访问的条目在链表末尾
    public LruCache(int capacity) {
        super(capacity, 0.75f, true);
        if (capacity <= 0) {
            throw new IllegalArgumentException("容量必须大于 0: " + capacity);
        }
        this.capacity = capacity;
    }

    // 每次 put 后调用：超出容量时淘汰链表头（最久未访问的条目）
    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity;
    }
}
