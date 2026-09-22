// project/src/main/java/com/example/vehicle/VehicleService.java —— 业务层
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（单元测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：roadmap 必会概念「Controller 不应写复杂业务」——三层分工：
//   Controller：HTTP 语义（路径/参数/状态码）        → VehicleController
//   Service：业务规则（校验/事务边界/领域决策）        → 本类
//   Store：数据访问（存取细节）                       → VehicleStore
// 业务异常抛给全局异常处理器统一转响应（ph14 的全局异常处理心智）。
package com.example.vehicle;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/** 车辆上报业务：校验 + 存取编排。 */
@Service
public class VehicleService {

    /** VIN 规则：17 位字母数字（教学简化，真实 VIN 有校验位算法）。 */
    static final java.util.regex.Pattern VIN_PATTERN =
            java.util.regex.Pattern.compile("^[A-HJ-NPR-Z0-9]{17}$");

    private final VehicleStore store;

    public VehicleService(VehicleStore store) {
        this.store = store;
    }

    /** 上报：校验 VIN/坐标/电量，落存储，返回带 id 的记录。 */
    public VehicleReport report(String vin, double lat, double lng, int speedKph, int batteryPct, long reportedAt) {
        if (vin == null || !VIN_PATTERN.matcher(vin).matches()) {
            throw new BusinessException("40001", "VIN 必须为 17 位字母数字");
        }
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            throw new BusinessException("40002", "经纬度越界");
        }
        if (speedKph < 0 || speedKph > 300) {
            throw new BusinessException("40003", "车速必须在 0~300 km/h");
        }
        if (batteryPct < 0 || batteryPct > 100) {
            throw new BusinessException("40004", "电量必须在 0~100%");
        }
        return store.save(vin, lat, lng, speedKph, batteryPct, reportedAt);
    }

    /** 最新状态：车辆无任何上报 → 404。 */
    public Optional<VehicleReport> latest(String vin) {
        return store.findLatest(vin);
    }

    /** 上报历史（默认最近 20 条）。 */
    public List<VehicleReport> history(String vin, Integer limit) {
        int n = (limit == null || limit <= 0 || limit > 100) ? 20 : limit;
        return store.findHistory(vin, n);
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
