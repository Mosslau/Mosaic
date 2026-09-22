// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.search.domain;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 设备事件领域模型（消费端反序列化目标；字段与 device-emitter 的 JSON 一一对应）。
 * 幂等键：(sn, seq) —— 同一设备同一序号的事件只处理一次（主文档 3.4）。
 */
public record DeviceEvent(
        @JsonProperty("eventId") String eventId,
        @JsonProperty("sn") String sn,
        @JsonProperty("seq") long seq,
        @JsonProperty("type") String type,
        @JsonProperty("severity") String severity,
        @JsonProperty("message") String message,
        @JsonProperty("ts") long ts) {

    /** 幂等键拼接（去重表与日志共用） */
    public String dedupKey() {
        return sn + ":" + seq;
    }
}
