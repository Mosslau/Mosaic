package com.example.ex05;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.SortOrder;
import co.elastic.clients.elasticsearch.core.IndexResponse;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.search.Hit;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;

import java.util.List;

/**
 * ES 8.x Java client 检索演示（主文档 3.8/3.9/3.10）：建索引/映射 -> 写 3 条日志 -> match/term/bool+range 查询。
 * 每次运行先删旧索引再重建（幂等，避免 mapping 冲突），再灌样例数据。
 * 验证环境：OpenJDK 17 + Maven 3.9 + co.elastic.clients:elasticsearch-java 8.13.4（pom 见本工程）。
 * 验证命令（需本地 ES，docker compose 见 examples/README.md）：
 *   mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex05.EsSearchDemo
 * 验证状态：未在本环境验证（需要 ES 8.x 服务）。
 */
public class EsSearchDemo {

    private static final String INDEX = "logs";

    public static void main(String[] args) throws Exception {
        // 1. 传输层：REST 客户端 + Jackson JSON 映射（8.x 官方客户端的标准装配）
        RestClient restClient = RestClient.builder(new HttpHost("localhost", 9200)).build();
        ElasticsearchTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
        try (ElasticsearchClient es = new ElasticsearchClient(transport)) {

            // 2. 删旧索引重建（幂等脚本）：映射 = message 分词(text) + level/service 精确(keyword) + ts 时间
            if (es.indices().exists(e -> e.index(INDEX)).value()) {
                es.indices().delete(d -> d.index(INDEX));
            }
            es.indices().create(c -> c.index(INDEX).mappings(m -> m
                    .properties("message", p -> p.text(t -> t))
                    .properties("level", p -> p.keyword(k -> k))
                    .properties("service", p -> p.keyword(k -> k))
                    .properties("ts", p -> p.date(d -> d))));
            System.out.println("index " + INDEX + " recreated（mapping: message=text, level/service=keyword, ts=date）");

            // 3. 写 3 条样例日志（id 用文档 id，天然幂等：同 id 重复写是覆盖不是重复）
            long now = System.currentTimeMillis();
            List<LogDoc> docs = List.of(
                    new LogDoc("log-1", "kafka consumer timeout, retry in 5s", "ERROR", "order-service", now - 60_000),
                    new LogDoc("log-2", "consumer group rebalance completed", "INFO", "order-service", now - 30_000),
                    new LogDoc("log-3", "elasticsearch index slow query", "WARN", "search-service", now - 10_000));
            for (LogDoc doc : docs) {
                IndexResponse resp = es.index(i -> i.index(INDEX).id(doc.id()).document(doc));
                System.out.printf("indexed id=%s result=%s%n", doc.id(), resp.result());
            }

            // 4a. match 全文检索：message 含 kafka（text 分词，查询文本也分词）
            searchAndPrint("match message=kafka",
                    es.search(s -> s.index(INDEX)
                            .query(q -> q.match(m -> m.field("message").query("kafka"))), LogDoc.class));

            // 4b. bool 组合：must(match "kafka") + filter(term level=ERROR)：过滤不算分但必须满足
            searchAndPrint("bool: match kafka AND term level=ERROR",
                    es.search(s -> s.index(INDEX).query(q -> q.bool(b -> b
                            .must(m -> m.match(t -> t.field("message").query("kafka")))
                            .filter(f -> f.term(t -> t.field("level").value("ERROR"))))), LogDoc.class));

            // 4c. bool + range 时间窗口 + sort：最近 1 小时的全部日志按时间倒序
            searchAndPrint("bool: range ts>=now-1h AND sort desc",
                    es.search(s -> s.index(INDEX)
                            .query(q -> q.bool(b -> b
                                    .filter(f -> f.range(r -> r.field("ts").gte("now-1h")))))
                            .sort(o -> o.field(f -> f.field("ts").order(SortOrder.Desc))), LogDoc.class));
        }
        System.out.println("done");
    }

    private static void searchAndPrint(String label, SearchResponse<LogDoc> resp) {
        System.out.println("-- " + label + " -> hits=" + resp.hits().hits().size());
        for (Hit<LogDoc> hit : resp.hits().hits()) {
            System.out.printf("   score=%.3f id=%s msg=%s level=%s%n",
                    hit.score() == null ? 0 : hit.score(),
                    hit.id(),
                    hit.source() == null ? "?" : hit.source().message(),
                    hit.source() == null ? "?" : hit.source().level());
        }
    }
}
