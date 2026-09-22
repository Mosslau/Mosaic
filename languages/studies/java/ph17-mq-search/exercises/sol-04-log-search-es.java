// exercises/sol-04-log-search-es.java —— 练习 4 参考实现：日志搜索（roadmap ph17 练习：日志搜索）
// 验证环境：OpenJDK 17 + Maven 3.9 + co.elastic.clients:elasticsearch-java 8.13.4（pom 复制 examples/ex05 的）
// 验证状态：未在本环境验证。需要本地 ES（examples/docker-compose.yml 起 elasticsearch）后
//   `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.logsearch.LogSearchDemo`
//   （联网环境去掉 -o 参数；elasticsearch-java 不在本机离线缓存，首次需联网拉取），未在本环境实测。
// 教学点：mapping 选型 text/keyword/date（主文档 3.8）、match/term/range/bool/aggs（3.9）、
//   ES 是最终一致的查询视图、主库在 MySQL（3.10）——本练习只做「检索视图」这一段。
// 输出预期（样例数据手算可核对）：service+level 过滤命中 1 条 ERROR、message 检索 kafka 命中 2 条、
//   level 聚合 = ERROR:2 INFO:3 WARN:1（样例造数见下）。

// =============================================================================
// 第一步：索引与映射（REST 版设计稿，与下方 Java 代码等价；对照主文档 3.8 的映射原语）
// =============================================================================
// PUT /app-logs
// {
//   "mappings": {
//     "properties": {
//       "message": { "type": "text" },        // 全文检索：分词后进倒排
//       "level":   { "type": "keyword" },      // 精确过滤 + 聚合：绝不用 text
//       "service": { "type": "keyword" },
//       "ts":      { "type": "date" }          // 时间范围：range 查询
//     }
//   }
// }
// 为什么 level/service 用 keyword 不用 text：term 查询与聚合要求「整串词项」，text 会被分词拆散
// （主文档 3.9：term 查 text 基本查不到）。level 枚举值少且固定，keyword 词典极小，查询极快。

// =============================================================================
// src/main/java/com/example/logsearch/LogEntry.java
// =============================================================================

package com.example.logsearch;

/** 日志文档模型（与 app-logs 索引映射一一对应） */
public record LogEntry(String id, String message, String level, String service, long ts) {
}

// =============================================================================
// src/main/java/com/example/logsearch/LogSearchService.java
// =============================================================================

package com.example.logsearch;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.SortOrder;
import co.elastic.clients.elasticsearch._types.aggregations.Aggregate;
import co.elastic.clients.elasticsearch._types.aggregations.StringTermsAggregate;
import co.elastic.clients.elasticsearch._types.aggregations.StringTermsBucket;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.search.Hit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 三个检索查询的实现（主文档 3.9 的 match/term/range/bool/aggs 全落一遍）。
 * 每个方法都注释了等价的 REST DSL，方便与文档逐字对照。
 */
public final class LogSearchService {

    private static final Logger log = LoggerFactory.getLogger(LogSearchService.class);

    private final ElasticsearchClient es;

    public LogSearchService(ElasticsearchClient es) {
        this.es = es;
    }

    /**
     * ① 最近 sinceMs 内 service + level 的日志，按 ts 倒序。
     * REST 等价：GET /app-logs/_search
     *   {"query":{"bool":{"filter":[{"term":{"service":"order-service"}},
     *                           {"term":{"level":"ERROR"}},
     *                           {"range":{"ts":{"gte":"now-1h"}}}]}},
     *    "sort":[{"ts":{"order":"desc"}}]}
     * filter 不算相关性分（纯过滤），bool 里过滤条件都用 filter 更高效。
     */
    public List<LogEntry> findByServiceAndLevel(String service, String level, long sinceMs) throws Exception {
        SearchResponse<LogEntry> resp = es.search(s -> s.index("app-logs")
                .query(q -> q.bool(b -> b
                        .filter(f -> f.term(t -> t.field("service").value(service)))
                        .filter(f -> f.term(t -> t.field("level").value(level)))
                        .filter(f -> f.range(r -> r.field("ts").gte(Instant.ofEpochMilli(sinceMs).toString())))))
                .sort(o -> o.field(f -> f.field("ts").order(SortOrder.Desc))), LogEntry.class);
        return hits(resp);
    }

    /**
     * ② message 关键词全文检索（match：查询文本分词后匹配，带相关性分）。
     * REST 等价：{"query":{"match":{"message":"kafka timeout"}}}
     */
    public List<LogEntry> searchMessage(String keyword) throws Exception {
        SearchResponse<LogEntry> resp = es.search(s -> s.index("app-logs")
                .query(q -> q.match(m -> m.field("message").query(keyword))), LogEntry.class);
        return hits(resp);
    }

    /**
     * ③ 按 level 分组统计（terms 聚合，等价 SQL: SELECT level, COUNT(*) FROM logs GROUP BY level）。
     * REST 等价：{"query":{"range":{"ts":{"gte":"now-1h"}}},"size":0,
     *            "aggs":{"byLevel":{"terms":{"field":"level"}}}}
     * size=0：只要聚合不要命中列表（省流量）。
     */
    public Map<String, Long> countByLevel(long sinceMs) throws Exception {
        SearchResponse<Void> resp = es.search(s -> s.index("app-logs")
                .query(q -> q.bool(b -> b
                        .filter(f -> f.range(r -> r.field("ts").gte(Instant.ofEpochMilli(sinceMs).toString())))))
                .size(0)
                .aggregations(a -> a.terms("byLevel", t -> t.field("level"))), Void.class);
        Map<String, Long> result = new LinkedHashMap<>();
        Aggregate agg = resp.aggregations().get("byLevel");
        if (agg != null && agg.isTerms()) {
            StringTermsAggregate terms = agg.terms();
            for (StringTermsBucket bucket : terms.buckets().array()) {
                result.put(bucket.key().stringValue(), bucket.docCount());
            }
        }
        return result;
    }

    private static List<LogEntry> hits(SearchResponse<LogEntry> resp) {
        return resp.hits().hits().stream()
                .map(Hit::source)
                .filter(java.util.Objects::nonNull)
                .toList();
    }
}

// =============================================================================
// src/main/java/com/example/logsearch/LogSearchDemo.java（可运行 main，需本地 ES）
// =============================================================================

package com.example.logsearch;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;

import java.util.List;

/**
 * 运行入口：建索引 -> 灌 6 条样例日志 -> 跑三个查询并打印。
 * 验证命令（需本地 ES，examples/docker-compose.yml 起 elasticsearch）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.logsearch.LogSearchDemo
 * 验证状态：未在本环境验证。
 */
public final class LogSearchDemo {

    private static final String INDEX = "app-logs";

    public static void main(String[] args) throws Exception {
        RestClient restClient = RestClient.builder(new HttpHost("localhost", 9200)).build();
        ElasticsearchTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
        try (ElasticsearchClient es = new ElasticsearchClient(transport)) {
            if (es.indices().exists(e -> e.index(INDEX)).value()) {
                es.indices().delete(d -> d.index(INDEX)); // 幂等重建，避免 mapping 冲突
            }
            es.indices().create(c -> c.index(INDEX).mappings(m -> m
                    .properties("message", p -> p.text(t -> t))
                    .properties("level", p -> p.keyword(k -> k))
                    .properties("service", p -> p.keyword(k -> k))
                    .properties("ts", p -> p.date(d -> d))));

            long now = System.currentTimeMillis();
            List<LogEntry> samples = List.of(
                    new LogEntry("l1", "kafka consumer timeout, retry scheduled", "ERROR", "order-service", now - 50_000),
                    new LogEntry("l2", "order created ok", "INFO", "order-service", now - 40_000),
                    new LogEntry("l3", "kafka consumer group rebalance", "WARN", "order-service", now - 30_000),
                    new LogEntry("l4", "index slow query detected", "WARN", "search-service", now - 20_000),
                    new LogEntry("l5", "search request completed", "INFO", "search-service", now - 10_000),
                    new LogEntry("l6", "health check ok", "INFO", "gateway-service", now - 5_000));
            for (LogEntry e : samples) {
                es.index(i -> i.index(INDEX).id(e.id()).document(e));
            }

            LogSearchService service = new LogSearchService(es);
            long since = now - 3_600_000; // 最近 1 小时

            System.out.println("-- ① order-service 最近 1h ERROR（按 ts 倒序）：");
            service.findByServiceAndLevel("order-service", "ERROR", since)
                    .forEach(e -> System.out.printf("   %s %s %s%n", e.ts(), e.level(), e.message()));
            System.out.println("-- ② message 含 kafka（match，带相关性）：");
            service.searchMessage("kafka").forEach(e -> System.out.printf("   %s %s %s%n", e.level(), e.service(), e.message()));
            System.out.println("-- ③ 最近 1h 按 level 聚合：");
            service.countByLevel(since).forEach((k, v) -> System.out.printf("   %s=%d%n", k, v));
        }
    }
}

// =============================================================================
// 预期输出（样例数据手算）：① 命中 l1（ERROR）；② 命中 l1、l3（含 kafka）；③ ERROR=1 INFO=3 WARN=2
// 若与预期不符，先查：样例 ts 是否都在窗口内（now-1h）、mapping 是否按上方设计建（text/keyword 配错最常见）。
