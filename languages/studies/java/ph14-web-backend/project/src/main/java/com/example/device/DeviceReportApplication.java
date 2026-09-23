// project/src/main/java/com/example/device/DeviceReportApplication.java —— 启动类
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test + spring-boot:run + curl 实测，见 README）
package com.example.device;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** 设备数据上报 API 入口。 */
@SpringBootApplication
public class DeviceReportApplication {
    public static void main(String[] args) {
        SpringApplication.run(DeviceReportApplication.class, args);
    }
}
