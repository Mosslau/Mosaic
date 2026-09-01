// project/src/main/java/com/example/vehicle/VehicleStore.java —— 内存车辆数据存储
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（单元测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：本阶段项目聚焦 Web 层，数据层用内存 Map 模拟「数据访问接口」——
// 接口形状（save/findLatest/findHistory）与真实数据层一致，ph13 的 HikariCP+JDBC
// 实现可以直接替换进来（ph15 讲框架级数据访问）。并发用 ConcurrentHashMap +
// AtomicLong 保证线程安全（ph09 并发阶段的心智）。
package com.example.vehicle;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/** 车辆上报的线程安全内存存储（数据层接口的最小实现）。 */
@Component
public class VehicleStore {

    private final Map<String, List<VehicleReport>> byVin = new ConcurrentHashMap<>();
    private final AtomicLong seq = new AtomicLong(1);

    /** 保存一条上报，返回带服务端分配 id 的记录。 */
    public VehicleReport save(String vin, double lat, double lng, int speedKph, int batteryPct, long reportedAt) {
        VehicleReport report = new VehicleReport(seq.getAndIncrement(), vin, lat, lng, speedKph, batteryPct, reportedAt);
        byVin.computeIfAbsent(vin, k -> new ArrayList<>()).add(report);
        return report;
    }

    /** 某辆车的最新一条上报（按上报时间最新；同秒内按 id 更大者最新）。 */
    public Optional<VehicleReport> findLatest(String vin) {
        List<VehicleReport> list = byVin.get(vin);
        if (list == null || list.isEmpty()) return Optional.empty();
        return list.stream().max(Comparator
                .comparingLong(VehicleReport::reportedAt)
                .thenComparingLong(VehicleReport::id));
    }

    /** 某辆车的上报历史（按时间升序；limit 限制条数）。 */
    public List<VehicleReport> findHistory(String vin, int limit) {
        List<VehicleReport> list = byVin.get(vin);
        if (list == null || list.isEmpty()) return List.of();
        List<VehicleReport> sorted = new ArrayList<>(list);
        sorted.sort(Comparator.comparingLong(VehicleReport::reportedAt));
        return sorted.subList(Math.max(0, sorted.size() - limit), sorted.size());
    }

    /** 某辆车是否已存在（用于 VIN 格式外的业务约束，如车辆未注册）。 */
    public boolean exists(String vin) {
        return byVin.containsKey(vin);
    }
}
