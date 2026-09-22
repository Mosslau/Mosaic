// 验证环境：OpenJDK 17 + Maven 3.9 + elasticsearch-java 8.13.4；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证（模式 B 需 docker compose 起 ES，app.search.engine=es）
package com.example.device.search.index;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.SortOrder;
import co.elastic.clients.elasticsearch._types.aggregations.Aggregate;
import co.elastic.clients.elasticsearch._types.aggregations.StringTermsAggregate;
import co.elastic.clients.elasticsearch._types.aggregations.StringTermsBucket;
import co.elastic.clients.elasticsearch.core.GetResponse;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.search.Hit;
import com.example.device.search.domain.DeviceEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * ES 索引引擎：真实索引 device-events（message text 全文检索 / type、severity、sn keyword / ts date），
 * 对应主文档 3.8/3.9 的映射与查询。索引与分片规划属 ph19，这里只建单节点索引。
 * 写入语义：文档 id = eventId -> 重复写是覆盖（幂等写入，主文档 3.10「最终一致视图」的落点）。
 */
public final class EsEventIndexer implements EventIndexer {

    private static final Logger log = LoggerFactory.getLogger(EsEventIndexer.class);
    private static final String INDEX = "device-events";

    private final ElasticsearchClient es;

    public EsEventIndexer(ElasticsearchClient es) {
        this.es = es;
        ensureIndex();
    }

    /** 启动时确保索引存在（幂等）；mapping 与主文档 3.8 原语一致 */
    private void ensureIndex() {
        try {
            boolean exists = es.indices().exists(e -> e.index(INDEX)).value();
            if (!exists) {
                es.indices().create(c -> c.index(INDEX).mappings(m -> m
                        .properties("eventId", p -> p.keyword(k -> k))
                        .properties("sn", p -> p.keyword(k -> k))
                        .properties("seq", p -> p.long_(l -> l))
                        .properties("type", p -> p.keyword(k -> k))
                        .properties("severity", p -> p.keyword(k -> k))
                        .properties("message", p -> p.text(t -> t))
                        .properties("ts", p -> p.date(d -> d))));
                log.info("index {} created", INDEX);
            }
        } catch (Exception e) {
            // ES 不可用：构造时只警告不炸——消费端写索引失败时会走重试路径（见 KafkaDeviceEventConsumer）
            log.warn("ES not reachable yet, index {} will be created on first write: {}", INDEX, e.getMessage());
        }
    }

    @Override
    public void index(DeviceEvent event) {
        try {
            es.index(i -> i.index(INDEX).id(event.eventId()).document(event));
        } catch (Exception e) {
            throw new IllegalStateException("es index failed for " + event.dedupKey(), e);
        }
    }

    @Override
    public Optional<DeviceEvent> findById(String eventId) {
        try {
            GetResponse<DeviceEvent> resp = es.get(g -> g.index(INDEX).id(eventId), DeviceEvent.class);
            return resp.found() ? Optional.ofNullable(resp.source()) : Optional.empty();
        } catch (Exception e) {
            throw new IllegalStateException("es get failed: " + eventId, e);
        }
    }

    @Override
    public List<DeviceEvent> search(String q, String type, String severity) {
        try {
            SearchResponse<DeviceEvent> resp = es.search(s -> {
                var b = s.index(INDEX);
                // q 走 message 全文检索（match）；type/severity 走 filter 精确过滤（term，不算分）
                boolean hasQuery = q != null && !q.isBlank();
                boolean hasType = type != null && !type.isBlank();
                boolean hasSeverity = severity != null && !severity.isBlank();
                if (hasQuery || hasType || hasSeverity) {
                    b.query(qb -> qb.bool(bb -> {
                        if (hasQuery) {
                            bb.must(m -> m.match(t -> t.field("message").query(q)));
                        }
                        if (hasType) {
                            bb.filter(f -> f.term(t -> t.field("type").value(type)));
                        }
                        if (hasSeverity) {
                            bb.filter(f -> f.term(t -> t.field("severity").value(severity)));
                        }
                        return bb;
                    }));
                }
                b.sort(o -> o.field(f -> f.field("ts").order(SortOrder.Desc)));
                return b;
            }, DeviceEvent.class);
            return resp.hits().hits().stream().map(Hit::source).filter(Objects::nonNull).toList();
        } catch (Exception e) {
            throw new IllegalStateException("es search failed", e);
        }
    }

    @Override
    public Map<String, Long> countBySeverity() {
        try {
            SearchResponse<Void> resp = es.search(s -> s.index(INDEX)
                    .size(0)
                    .aggregations(a -> a.terms("bySeverity", t -> t.field("severity"))), Void.class);
            Map<String, Long> counts = new LinkedHashMap<>();
            Aggregate agg = resp.aggregations().get("bySeverity");
            if (agg != null && agg.isTerms()) {
                StringTermsAggregate terms = agg.terms();
                for (StringTermsBucket bucket : terms.buckets().array()) {
                    counts.put(bucket.key().stringValue(), bucket.docCount());
                }
            }
            return counts;
        } catch (Exception e) {
            throw new IllegalStateException("es count failed", e);
        }
    }
}
