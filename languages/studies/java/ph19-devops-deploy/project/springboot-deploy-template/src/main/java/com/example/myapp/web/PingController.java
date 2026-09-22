package com.example.myapp.web;

import java.time.Instant;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 极简探活/自描述端点：/ping 返回运行配置（app 名、profile、时间），供部署探活与「配置是否注入成功」验证。
 * 对应主文档 3.2「jar 不变，配置随环境注入」：这里的 profile/name 由环境变量/启动参数覆盖。
 * 验证状态：未在本环境验证（需 mvn + Boot 依赖）
 */
@RestController
public class PingController {

    @Value("${spring.application.name:myapp}")
    private String appName;

    @Value("${spring.profiles.active:dev}")
    private String profile;

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "app", appName,
                "profile", profile,
                "ts", Instant.now().toString());
    }
}
