// project/ttl-cache-app.java —— 泛型 TTL 缓存自测入口
// 覆盖七条路径：基础命中、TTL 过期惰性删除、覆盖刷新 TTL、remove/containsKey/clear、purgeExpired 批量清理、泛型类型安全、非法 TTL 校验
// 验证环境：OpenJDK 17.0.16
// 编译：javac ttl-cache.java ttl-cache-app.java
// 运行：java TtlCacheApp
// 验证状态：已验证：OpenJDK 17.0.16
class TtlCacheApp {
    public static void main(String[] args) throws InterruptedException {
        TtlCache<String, String> cache = new TtlCache<>();

        // 路径 1：基础 put/get 命中
        cache.put("k1", "v1", 10_000);
        check("v1".equals(cache.get("k1")), "基础命中: get(k1)=v1");

        // 路径 2：TTL 过期——短 TTL 先命中，睡过后 miss，且惰性删除已生效
        cache.put("temp", "temp-v", 80);
        check("temp-v".equals(cache.get("temp")), "短 TTL 未过期时命中");
        Thread.sleep(200);
        check(cache.get("temp") == null, "过期后 get 返回 null");
        check(cache.size() == 1, "惰性删除后 size 回到 1");

        // 路径 3：同 key 覆盖会刷新 TTL——覆盖后重新计时
        cache.put("k1", "v2", 120);
        Thread.sleep(60);
        check("v2".equals(cache.get("k1")), "覆盖后读到新值 v2");
        Thread.sleep(100);
        check(cache.get("k1") == null, "覆盖后 TTL 重新计时，过期被惰性删除");

        // 路径 4：remove / containsKey / clear
        cache.put("a", "1", 10_000);
        cache.put("b", "2", 10_000);
        check(cache.containsKey("a"), "containsKey(a) 命中");
        cache.remove("a");
        check(!cache.containsKey("a") && cache.size() == 1, "remove 后 containsKey 为 false、size 减一");
        cache.clear();
        check(cache.isEmpty(), "clear 后为空");

        // 路径 5：purgeExpired 批量清理——过期但未访问时 size 不变，purge 后清空
        cache.put("x", "1", 50);
        cache.put("y", "2", 50);
        Thread.sleep(120);
        check(cache.size() == 2, "过期但未清理时 size 仍为 2（惰性策略不主动清扫）");
        int removed = cache.purgeExpired();
        check(removed == 2 && cache.isEmpty(), "purgeExpired 清理 2 个过期条目后为空");

        // 路径 6：泛型类型安全——Integer 键值同样工作
        TtlCache<Integer, Integer> intCache = new TtlCache<>();
        intCache.put(1, 100, 10_000);
        check(Integer.valueOf(100).equals(intCache.get(1)), "Integer 键值缓存命中");

        // 路径 7：非法 TTL 校验
        try {
            cache.put("bad", "v", 0);
            throw new AssertionError("自测失败: ttlMillis=0 应抛 IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            System.out.println("通过: ttlMillis=0 抛出 IllegalArgumentException");
        }

        System.out.println("全部自测通过");
    }

    // 断言失败立即抛 AssertionError 并给出路径名（不静默），全部通过则打印「全部自测通过」
    private static void check(boolean condition, String msg) {
        if (!condition) {
            throw new AssertionError("自测失败: " + msg);
        }
        System.out.println("通过: " + msg);
    }
}
