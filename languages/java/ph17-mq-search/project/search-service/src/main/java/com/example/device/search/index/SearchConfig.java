// 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.search.index;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import com.example.device.search.consume.DeviceEventDedup;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 引擎装配：app.search.engine=memory（默认，matchIfMissing）或 es，二选一注册 EventIndexer。
 * 默认 memory 让无中间件环境开箱可跑（project/README 模式 A）；切 es 走完整链路（模式 B）。
 */
@Configuration
public class SearchConfig {

    /** (sn,seq) 去重器：两个引擎共用（消费端先于索引去重） */
    @Bean
    public DeviceEventDedup deviceEventDedup() {
        return new DeviceEventDedup();
    }

    @Bean
    @ConditionalOnProperty(name = "app.search.engine", havingValue = "memory", matchIfMissing = true)
    public EventIndexer inMemoryEventIndexer() {
        return new InMemoryEventIndexer();
    }

    @Bean(destroyMethod = "close")
    @ConditionalOnProperty(name = "app.search.engine", havingValue = "es")
    public ElasticsearchClient esClient(@Value("${app.es.host:localhost}") String host,
                                        @Value("${app.es.port:9200}") int port) {
        RestClient restClient = RestClient.builder(new HttpHost(host, port)).build();
        ElasticsearchTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
        return new ElasticsearchClient(transport);
    }

    @Bean
    @ConditionalOnProperty(name = "app.search.engine", havingValue = "es")
    public EventIndexer esEventIndexer(ElasticsearchClient esClient) {
        return new EsEventIndexer(esClient);
    }
}
