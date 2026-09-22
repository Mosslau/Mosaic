// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见本模块 pom.xml 与 examples/README.md
// 验证状态：未在本环境验证
package com.example.ex02;

/** 订单创建事件（与 ex01 ProducerMain 发的 JSON 对应：orderId/userId/amount） */
public record OrderEvent(String orderId, String userId, int amount) {
}
