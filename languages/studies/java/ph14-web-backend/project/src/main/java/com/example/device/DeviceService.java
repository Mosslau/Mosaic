// project/src/main/java/com/example/device/DeviceService.java —— 业务层
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（单元测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：roadmap 必会概念「Controller 不应写复杂业务」——三层分工：
//   Controller：HTTP 语义（路径/参数/状态码）        → DeviceController
//   Service：业务规则（校验/事务边界/领域决策）        → 本类
//   Store：数据访问（存取细节）                       → DeviceStore
// 业务异常抛给全局异常处理器统一转响应（ph14 的全局异常处理心智）。
package com.example.device;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/** 设备上报业务：校验 + 存取编排。 */
@Service
public class DeviceService {

    /** DEVICE_ID 规则：17 位字母数字（教学简化，真实 DEVICE_ID 有校验位算法）。 */
    static final java.util.regex.Pattern DEVICE_ID_PATTERN =
            java.util.regex.Pattern.compile("^[A-HJ-NPR-Z0-9]{17}$");

    private final DeviceStore store;

    public DeviceService(DeviceStore store) {
        this.store = store;
    }

    /** 上报：校验 DEVICE_ID/坐标/电量，落存储，返回带 id 的记录。 */
    public DeviceReport report(String device_id, double lat, double lng, int speedKph, int componentPct, long reportedAt) {
        if (device_id == null || !DEVICE_ID_PATTERN.matcher(device_id).matches()) {
            throw new BusinessException("40001", "DEVICE_ID 必须为 17 位字母数字");
        }
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            throw new BusinessException("40002", "经纬度越界");
        }
        if (speedKph < 0 || speedKph > 300) {
            throw new BusinessException("40003", "运行速度必须在 0~300 km/h");
        }
        if (componentPct < 0 || componentPct > 100) {
            throw new BusinessException("40004", "电量必须在 0~100%");
        }
        return store.save(device_id, lat, lng, speedKph, componentPct, reportedAt);
    }

    /** 最新状态：设备无任何上报 → 404。 */
    public Optional<DeviceReport> latest(String device_id) {
        return store.findLatest(device_id);
    }

    /** 上报历史（默认最近 20 条）。 */
    public List<DeviceReport> history(String device_id, Integer limit) {
        int n = (limit == null || limit <= 0 || limit > 100) ? 20 : limit;
        return store.findHistory(device_id, n);
    }

    /** 业务异常：code 是业务错误码字符串，由全局异常处理器映射 HTTP 状态。 */
    public static class BusinessException extends RuntimeException {
        private final String code;
        public BusinessException(String code, String message) {
            super(message);
            this.code = code;
        }
        public String getCode() {
            return code;
        }
    }
}
