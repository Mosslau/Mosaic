package com.example;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.env.Environment;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.Map;

/**
 * 演示端点：把「当前 profile + 类型安全配置 + 条件装配结果」一起暴露，
 * 供 curl 与测试核对 dev/prod 两套环境的行为差异。
 */
@RestController
public class GreetingController {

    private final GreetingProperties properties;
    private final Environment environment;
    private final ObjectProvider<FeatureConfig.ExtraFeatureBean> feature;

    public GreetingController(GreetingProperties properties,
                              Environment environment,
                              ObjectProvider<FeatureConfig.ExtraFeatureBean> feature) {
        this.properties = properties;
        this.environment = environment;
        this.feature = feature;
    }

    @GetMapping("/api/greeting")
    public Map<String, Object> greeting() {
        return Map.of(
                "profile", Arrays.toString(environment.getActiveProfiles()),
                "message", properties.message(),
                "featureEnabled", properties.featureEnabled(),
                "featureBeanPresent", feature.getIfAvailable() != null
        );
    }
}
