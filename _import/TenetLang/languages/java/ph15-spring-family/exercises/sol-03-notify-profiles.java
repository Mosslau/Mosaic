// exercises/sol-03-notify-profiles.java —— 练习 3 参考实现：profile + 条件装配 + 类型安全配置（通知服务）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0（starter-web/test，离线实测）
// 验证状态：已验证（本机离线 mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 2, Failures: 0, Errors: 0
//   （NotifyProfileTest.devProfileEnablesSmsChannel：默认 dev → {"enabled":true,"channel":"sms","smsSenderPresent":true}
//     ProdNotifyProfileTest.prodProfileTurnsSmsOff：prod → {"enabled":false,"channel":"email","smsSenderPresent":false}）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex02-.../pom.xml 并删掉 actuator 依赖，
//   artifactId 改 sol03-notify-profiles；hsqldb 仲裁项可留可删）+ 下列文件。验证命令：
//   mvn -o -Dmaven.repo.local=/tmp/m2clone test；运行：spring-boot:run -Dspring-boot.run.profiles=dev/prod
//   （dev 端口 18102 / prod 端口 18103）。
// 教学点：同一 jar 两套环境——profile 文件按「环境」切配置，@ConfigurationProperties 提供强类型读取，
//   @ConditionalOnProperty 按开关决定 Bean 是否存在（与 ex01 的 @Conditional、ex02 的 feature 开关同一机制）。
// ===========================================================================
// src/main/resources/application.properties
// ===========================================================================
spring.profiles.active=dev
notify.enabled=false
notify.channel=email

// ===========================================================================
// src/main/resources/application-dev.properties
// ===========================================================================
server.port=18102
notify.enabled=true
notify.channel=sms

// ===========================================================================
// src/main/resources/application-prod.properties
// ===========================================================================
server.port=18103
notify.enabled=false
notify.channel=email

// ===========================================================================
// src/main/java/com/example/notify/NotifyApp.java
// ===========================================================================
package com.example.notify;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class NotifyApp {

    public static void main(String[] args) {
        SpringApplication.run(NotifyApp.class, args);
    }
}

// ===========================================================================
// src/main/java/com/example/notify/NotifyProperties.java
// ===========================================================================
package com.example.notify;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** 通知开关与通道：notify.enabled / notify.channel（dev 短信、prod 关闭） */
@ConfigurationProperties(prefix = "notify")
public record NotifyProperties(boolean enabled, String channel) {
}

// ===========================================================================
// src/main/java/com/example/notify/NotifyConfig.java
// ===========================================================================
package com.example.notify;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 条件装配：notify.enabled=true 才注册短信发送 Bean（dev 开 / prod 关） */
@Configuration
public class NotifyConfig {

    @Bean
    @ConditionalOnProperty(name = "notify.enabled", havingValue = "true")
    public SmsSender smsSender() {
        return new SmsSender();
    }

    public record SmsSender() {
    }
}

// ===========================================================================
// src/main/java/com/example/notify/NotifyController.java
// ===========================================================================
package com.example.notify;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 暴露当前配置形状：channel 来自 @ConfigurationProperties，senderPresent 来自条件装配 */
@RestController
public class NotifyController {

    private final NotifyProperties properties;
    private final ObjectProvider<NotifyConfig.SmsSender> smsSender;

    public NotifyController(NotifyProperties properties, ObjectProvider<NotifyConfig.SmsSender> smsSender) {
        this.properties = properties;
        this.smsSender = smsSender;
    }

    @GetMapping("/api/notify")
    public Map<String, Object> notifyConfig() {
        return Map.of(
                "enabled", properties.enabled(),
                "channel", properties.channel(),
                "smsSenderPresent", smsSender.getIfAvailable() != null);
    }
}

// ===========================================================================
// src/test/java/com/example/notify/NotifyProfileTest.java
// ===========================================================================
package com.example.notify;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * sol-03 测试：dev 开短信 / prod 关短信，配置形状随 profile 切换。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class NotifyProfileTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void devProfileEnablesSmsChannel() throws Exception {
        mockMvc.perform(get("/api/notify"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(true))
                .andExpect(jsonPath("$.channel").value("sms"))
                .andExpect(jsonPath("$.smsSenderPresent").value(true));
    }

}

// ===========================================================================
// src/test/java/com/example/notify/ProdNotifyProfileTest.java
// ===========================================================================
package com.example.notify;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** prod profile：短信 Bean 被摘掉、通道回 email */
@SpringBootTest(properties = "spring.profiles.active=prod")
@AutoConfigureMockMvc
class ProdNotifyProfileTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void prodProfileTurnsSmsOff() throws Exception {
        mockMvc.perform(get("/api/notify"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(false))
                .andExpect(jsonPath("$.channel").value("email"))
                .andExpect(jsonPath("$.smsSenderPresent").value(false));
    }
}

