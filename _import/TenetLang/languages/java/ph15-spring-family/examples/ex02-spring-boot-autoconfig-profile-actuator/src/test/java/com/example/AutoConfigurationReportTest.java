package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionEvaluationReport;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 「自动配置要能追踪来源」的实测：容器启动后把自动配置条件报告（ConditionEvaluationReport）
 * 拿出来数——多少自动配置类被「全条件命中」（positive match）。这是 roadmap 必会概念
 * 「Spring Boot 自动配置要能追踪来源」的自动化版本：不靠猜，报告里查得到。
 * 启动时加 --debug（或 logging.level...ConditionEvaluationReportLogger=DEBUG）会把同一份
 * 报告以「Positive matches / Negative matches」两段打到日志（examples/README 有运行实录）。
 */
@SpringBootTest
class AutoConfigurationReportTest {

    @Autowired
    private ConditionEvaluationReport report;

    @Test
    void webAutoConfigurationsArePositiveMatches() {
        var bySource = report.getConditionAndOutcomesBySource();
        long positiveMatches = bySource.entrySet().stream()
                .filter(e -> e.getValue().isFullMatch())
                .count();
        System.out.println("[自动配置报告] positive-match 自动配置类数量 = " + positiveMatches);
        // 有 web + actuator 的 classpath，MVC/DispatcherServlet/Health 三件自动配置必须全命中
        var webMvc = bySource.get(
                "org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration");
        var dispatcher = bySource.get(
                "org.springframework.boot.autoconfigure.web.servlet.DispatcherServletAutoConfiguration");
        var actuatorHealth = bySource.get(
                "org.springframework.boot.actuate.autoconfigure.health.HealthEndpointAutoConfiguration");
        assertThat(webMvc).isNotNull();
        assertThat(webMvc.isFullMatch()).isTrue();
        assertThat(dispatcher).isNotNull();
        assertThat(dispatcher.isFullMatch()).isTrue();
        assertThat(actuatorHealth).isNotNull();
        assertThat(actuatorHealth.isFullMatch()).isTrue();
    }
}
