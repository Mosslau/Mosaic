// exercises/sol-04-redis-cache.java —— 练习 4 参考实现：Redis Cache-Aside 缓存（本机 redis-server + Jedis）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + Jedis 3.9.0 + 本机 redis-server（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS；redis-server 实测拉起端口 6399）
// 实测结果：Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
// 前置条件：本机安装 redis-server（macOS: brew install redis；Linux: apt install redis-server）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol04-redis-cache</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>redis.clients</groupId>
//         <artifactId>jedis</artifactId>
//         <version>3.9.0</version>
//       </dependency>
//       <dependency>
//         <groupId>org.junit.jupiter</groupId>
//         <artifactId>junit-jupiter</artifactId>
//         <version>5.10.1</version>
//         <scope>test</scope>
//       </dependency>
//     </dependencies>
//     <build>
//       <plugins>
//         <plugin>
//           <groupId>org.apache.maven.plugins</groupId>
//           <artifactId>maven-surefire-plugin</artifactId>
//           <version>3.2.5</version>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 本文件内容放 src/main/java/com/example/RedisCache.java
//
// 测试基础设施（src/test/java/com/example/RedisServerHandle.java）:
//   —— 与 examples/ex05-redis 同款：ProcessBuilder 起独立端口 6399 的真实 redis-server，
//      轮询端口可连即就绪；redis-server 不在 PATH 时报错提示安装。
//
//   package com.example;
//   import java.io.IOException;
//   import java.net.Socket;
//
//   final class RedisServerHandle {
//       static final int PORT = 6399;
//       private final Process process;
//       private RedisServerHandle(Process process) { this.process = process; }
//
//       static RedisServerHandle start() throws IOException, InterruptedException {
//           Process process = new ProcessBuilder(
//                   "redis-server", "--port", String.valueOf(PORT),
//                   "--save", "", "--appendonly", "no", "--daemonize", "no")
//                   .redirectErrorStream(true).start();
//           long deadline = System.currentTimeMillis() + 10_000;
//           while (System.currentTimeMillis() < deadline) {
//               try (Socket s = new Socket("127.0.0.1", PORT)) {
//                   return new RedisServerHandle(process);
//               } catch (IOException refused) {
//                   if (!process.isAlive()) {
//                       throw new IOException("redis-server 启动失败，退出码 " + process.exitValue()
//                               + "（请确认已安装 redis-server）");
//                   }
//                   Thread.sleep(100);
//               }
//           }
//           process.destroyForcibly();
//           throw new IOException("等待 redis-server 就绪超时");
//       }
//
//       void stop() { process.destroy(); }
//   }
//
// 测试类（src/test/java/com/example/RedisCacheTest.java）:
//
//   package com.example;
//   import static org.junit.jupiter.api.Assertions.*;
//   import java.io.IOException;
//   import java.util.HashMap;
//   import java.util.Map;
//   import org.junit.jupiter.api.*;
//   import redis.clients.jedis.Jedis;
//
//   class RedisCacheTest {
//       private static RedisServerHandle server;
//
//       @BeforeAll static void startRedis() throws IOException, InterruptedException {
//           server = RedisServerHandle.start();
//       }
//       @AfterAll static void stopRedis() { server.stop(); }
//
//       @Test void setGetDel_roundTrip() {
//           try (Jedis jedis = new Jedis("127.0.0.1", RedisServerHandle.PORT)) {
//               assertEquals("PONG", jedis.ping());
//               assertEquals("OK", jedis.set("greeting", "你好 Redis"));
//               assertEquals("你好 Redis", jedis.get("greeting"));
//               assertEquals(1L, jedis.del("greeting"));
//               assertNull(jedis.get("greeting"), "删除后 GET 应返回 nil");
//           }
//       }
//
//       @Test void cacheAside_hitDoesNotHitSource() {
//           Map<String, String> database = new HashMap<>();
//           database.put("user:42", "{\"name\":\"mosslau\"}");
//           RedisCache cache = new RedisCache("127.0.0.1", RedisServerHandle.PORT);
//           try {
//               String key = "cache:user:42";
//               cache.del(key);
//               // 第一次：缓存未命中 → 回源 → 回填缓存（带 60 秒过期兜底）
//               assertEquals("{\"name\":\"mosslau\"}", cache.cacheAsideGet(key, () -> database.get("user:42")));
//               // 第二次：删掉「数据库」，缓存仍命中——证明读的是缓存不是库
//               database.clear();
//               assertEquals("{\"name\":\"mosslau\"}", cache.cacheAsideGet(key, () -> database.get("user:42")));
//               assertEquals(60L, cache.ttl(key), "回填应带 60 秒过期兜底");
//           } finally {
//               cache.close();
//           }
//       }
//
//       @Test void ttl_semantics() {
//           try (Jedis jedis = new Jedis("127.0.0.1", RedisServerHandle.PORT)) {
//               jedis.setex("session:u1", 60, "token-abc");
//               long ttl = jedis.ttl("session:u1");
//               assertTrue(ttl > 0 && ttl <= 60, "TTL 应在 (0, 60] 区间，实测 " + ttl);
//               assertEquals(-2L, jedis.ttl("no-such-key"), "不存在的键 TTL 为 -2");
//               jedis.del("session:u1");
//           }
//       }
//   }
//
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - Cache-Aside 三步：先查缓存 → 未命中回源（数据库）→ 回填缓存（setex 带 TTL 防脏数据永生）
//   - 第二次命中时删掉「数据库」仍能读到值——证明读的是缓存不是库
//   - 不测 mock 出来的 Redis，测真实服务：测试临时拉起独立端口，互不污染
//   - TTL 语义：存在的键返回剩余秒数（>0 且 <= 设定的 60）；不存在的键返回 -2
// ---------------------------------------------------------------------------

package com.example;

import java.io.Closeable;
import java.util.function.Supplier;
import redis.clients.jedis.Jedis;

/** 练习 4 参考实现：Redis Cache-Aside 缓存封装 */
public class RedisCache implements Closeable {

    private final String host;
    private final int port;

    public RedisCache(String host, int port) {
        this.host = host;
        this.port = port;
    }

    /** Cache-Aside 读：先查缓存，未命中回源并回填（60 秒过期兜底） */
    public String cacheAsideGet(String key, Supplier<String> loader) {
        try (Jedis jedis = new Jedis(host, port)) {
            String cached = jedis.get(key);
            if (cached != null) {
                return cached;
            }
            String loaded = loader.get();
            if (loaded != null) {
                jedis.setex(key, 60, loaded);   // setex = set + expire，一条命令设置值与 TTL
            }
            return loaded;
        }
    }

    public void del(String key) {
        try (Jedis jedis = new Jedis(host, port)) {
            jedis.del(key);
        }
    }

    public long ttl(String key) {
        try (Jedis jedis = new Jedis(host, port)) {
            return jedis.ttl(key);
        }
    }

    @Override
    public void close() {
        // Jedis 每次操作即开即关（连接池语义由 JedisPool 提供，本练习从简）；
        // 真实工程用 JedisPool 复用连接，见 examples/ex05 的 JedisClientTest 思路
    }
}
