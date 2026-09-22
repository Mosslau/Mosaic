// 验证环境：OpenJDK 17 + Maven 3.9；构建/运行命令见本模块 pom.xml 与 examples/README.md
// 验证状态：未在本环境验证
package com.example.ex05;

/** 日志文档模型（与主文档 3.8 的 mapping 对应：message 分词全文检索、level/service 精确匹配、ts 时间范围） */
public record LogDoc(String id, String message, String level, String service, long ts) {
}
