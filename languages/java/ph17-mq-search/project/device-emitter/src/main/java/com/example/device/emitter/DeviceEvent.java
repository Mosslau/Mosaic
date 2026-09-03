// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见 device-emitter/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.emitter;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 设备事件（与 search-service 的 DeviceEvent 字段一致；emitter 只负责序列化，不依赖 search-service）
 * eventId 由发送端生成（生产由设备/接入服务生成），消费端以 (sn,seq) 做幂等（主文档 3.4）。
 */
public record DeviceEvent(
        @JsonProperty("eventId") String eventId,
        @JsonProperty("sn") String sn,
        @JsonProperty("seq") long seq,
        @JsonProperty("type") String type,
        @JsonProperty("severity") String severity,
        @JsonProperty("message") String message,
        @JsonProperty("ts") long ts) {
}
