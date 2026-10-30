package com.ninebot.dataagent;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;

/**
 * 数据智能助手 Java 控制平面入口。
 *
 * <p>当前阶段将 Agent/Skill 控制、Python Runtime Client、MCP Gateway、
 * Sandbox Gateway 和 SSE Gateway 放在一个 Spring Boot 部署单元中，
 * 先完成清晰的模块边界，再根据流量和团队边界拆分服务。</p>
 */
@SpringBootApplication(exclude = DataSourceAutoConfiguration.class)
public class DataAgentApplication {
    public static void main(String[] args) {
        SpringApplication.run(DataAgentApplication.class, args);
    }
}
