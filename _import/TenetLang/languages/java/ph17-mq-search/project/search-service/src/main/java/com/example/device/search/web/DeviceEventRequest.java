// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见 search-service/pom.xml 与 project/README.md
// 验证状态：未在本环境验证
package com.example.device.search.web;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 事件注入请求体（POST /api/events，绕过 MQ 供无 Kafka 环境造数；完整链路的入口是 Kafka）。
 * seq 由服务端生成（全局递增近似）——真实设备的 seq 由设备维护（见 device-emitter 注释）。
 */
public record DeviceEventRequest(
        @JsonProperty("sn") String sn,
        @JsonProperty("type") String type,
        @JsonProperty("severity") String severity,
        @JsonProperty("message") String message) {
}
