// project/src/test/java/com/example/device/DeviceServiceTest.java —— Service 单元测试
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + JUnit Jupiter 5.10.2（本机离线 mvn -o 实测）
// 验证状态：已验证（mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 教学点：Service 层单元测试不启动 Spring（直接 new），聚焦业务规则：
// 合法上报落库、DEVICE_ID 非法、经纬度越界、运行速度/电量越界、无数据设备 latest 为空、
// 历史 limit 截断。
package com.example.device;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DeviceServiceTest {

    private DeviceService service;

    @BeforeEach
    void setUp() {
        service = new DeviceService(new DeviceStore());
    }

    @Test
    void reportValidSavesAndAssignsId() {
        DeviceReport r = service.report("LSVAB4BR0DA123456", 31.23, 121.47, 60, 88, 1_700_000_000L);
        assertThat(r.id()).isEqualTo(1);
        assertThat(r.device_id()).isEqualTo("LSVAB4BR0DA123456");
        assertThat(r.speedKph()).isEqualTo(60);
    }

    @Test
    void invalidDeviceIDRejected() {
        assertThatThrownBy(() -> service.report("SHORT", 0, 0, 0, 0, 1L))
                .isInstanceOf(DeviceService.BusinessException.class)
                .hasMessageContaining("DEVICE_ID");
    }

    @Test
    void outOfRangeCoordinatesRejected() {
        assertThatThrownBy(() -> service.report("LSVAB4BR0DA123456", 91.0, 121.47, 0, 0, 1L))
                .isInstanceOf(DeviceService.BusinessException.class)
                .hasMessageContaining("经纬度");
    }

    @Test
    void outOfRangeComponentRejected() {
        assertThatThrownBy(() -> service.report("LSVAB4BR0DA123456", 31.23, 121.47, 60, 150, 1L))
                .isInstanceOf(DeviceService.BusinessException.class)
                .hasMessageContaining("电量");
    }

    @Test
    void latestEmptyForUnknownDevice() {
        assertThat(service.latest("LSVAB4BR0DA999999")).isEmpty();
    }

    @Test
    void historyLimited() {
        for (int i = 0; i < 5; i++) {
            service.report("LSVAB4BR0DA123456", 31.23, 121.47, 10 + i, 90, 1_700_000_000L + i);
        }
        assertThat(service.history("LSVAB4BR0DA123456", 2)).hasSize(2);
        assertThat(service.latest("LSVAB4BR0DA123456")).isPresent();
    }
}
