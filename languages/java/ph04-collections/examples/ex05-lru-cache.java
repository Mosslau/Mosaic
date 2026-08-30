// examples/ex05-lru-cache.java —— LRU Cache：LinkedHashMap accessOrder=true + removeEldestEntry 淘汰
// 对应主文档「6. 代码示例 / 示例 5」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex05-lru-cache.java
// 运行：java LRUCache
// 已验证：本环境编译零错误，运行输出符合注释中的期望值
import java.util.*;

class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;

    public LRUCache(int capacity) {
        // accessOrder=true：按访问顺序排列，最近访问的在末尾
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }

    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity; // 超限时淘汰最久未访问条目（链表头部）
    }

    public static void main(String[] args) {
        LRUCache<String, String> cache = new LRUCache<>(3);
        cache.put("A", "设备A状态");
        cache.put("B", "设备B状态");
        cache.put("C", "设备C状态");
        System.out.println("初始缓存: " + cache.keySet());   // [A, B, C]

        cache.get("A"); // 访问 A —— A 移到链表末尾，变最新
        cache.put("D", "设备D状态"); // 插入 D —— 淘汰最久未用的 B
        System.out.println("访问 A 插入 D 后: " + cache.keySet());   // [C, A, D]

        cache.put("E", "设备E状态"); // 淘汰 C
        System.out.println("插入 E 后: " + cache.keySet());   // [A, D, E]
    }
}
