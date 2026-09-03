// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.search.index;

import com.example.device.search.domain.DeviceEvent;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 事件索引抽象：两档实现（内存 / ES）行为对齐，检索 API 不感知底层。
 * 双引擎的意义（project/README）：没有中间件也能跑通「事件 -> 索引 -> 检索」语义（memory），
 * 有 docker 则切 es 走真实检索——对应主文档 3.10「ES 是查询视图」的工程落法。
 */
public interface EventIndexer {

    /** 索引一条事件（消费端去重后调用）；同 eventId 重复写是覆盖（幂等写入） */
    void index(DeviceEvent event);

    /** 按 eventId 精确取一条（内存 Map / ES get 文档） */
    Optional<DeviceEvent> findById(String eventId);

    /**
     * 组合检索：q（关键词，message/type/sn 模糊匹配）+ type/severity 精确过滤（可空），按 ts 倒序。
     * 行为约定：两个引擎对同一批数据返回同一集合（排序一致），便于无中间件验收。
     */
    List<DeviceEvent> search(String q, String type, String severity);

    /** 按 severity 分组统计（对应 SQL GROUP BY，主文档 3.9 聚合） */
    Map<String, Long> countBySeverity();
}
