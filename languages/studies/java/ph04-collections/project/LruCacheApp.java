/* project/LruCacheApp.java —— LRU Cache 自测入口
 * 覆盖四条路径：命中刷新、LRU 淘汰顺序、覆盖已有 key 不涨容量、miss 返回 null，外加非法容量校验
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac LruCache.java LruCacheApp.java
 * 运行：java LruCacheApp
 * 验证状态：已验证：OpenJDK 17.0.16
 */
import java.util.ArrayList;

public class LruCacheApp {
    public static void main(String[] args) {
        // 路径 1：命中刷新 + LRU 淘汰顺序
        LruCache<String, String> cache = new LruCache<>(3);
        cache.put("A", "设备A状态");
        cache.put("B", "设备B状态");
        cache.put("C", "设备C状态");
        checkOrder(cache, "[A, B, C]", "初始装载");

        cache.get("A");                 // 命中 A：A 移到链表末尾，变为最新
        cache.put("D", "设备D状态");     // 超容量：淘汰最久未使用的 B
        checkOrder(cache, "[C, A, D]", "get(A) 后 put(D)，最久未用的 B 被淘汰");

        cache.put("E", "设备E状态");     // 继续超容量：淘汰 C
        checkOrder(cache, "[A, D, E]", "put(E) 淘汰 C");

        // 路径 2：覆盖已有 key 不涨容量
        cache.put("A", "设备A状态v2");
        check(cache.size() == 3, "覆盖已有 key 不涨容量");
        check("设备A状态v2".equals(cache.get("A")), "覆盖后读到新值");

        // 路径 3：miss 返回 null
        check(cache.get("X") == null, "不存在的 key 返回 null");

        // 路径 4：非法容量校验
        try {
            new LruCache<String, String>(0);
            throw new AssertionError("自测失败: 容量 0 应抛 IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            System.out.println("通过: 容量 0 抛出 IllegalArgumentException");
        }

        System.out.println("全部自测通过");
    }

    // 断言 keySet 的顺序恰好等于期望列表（keySet 自身是 Set，equals 不比较顺序，故转 List 再比）
    private static void checkOrder(LruCache<String, String> cache, String expected, String msg) {
        String actual = new ArrayList<>(cache.keySet()).toString();
        if (!actual.equals(expected)) {
            throw new AssertionError("自测失败: " + msg + "，期望 " + expected + "，实际 " + actual);
        }
        System.out.println("通过: " + msg + " → " + actual);
    }

    private static void check(boolean condition, String msg) {
        if (!condition) {
            throw new AssertionError("自测失败: " + msg);
        }
        System.out.println("通过: " + msg);
    }
}
