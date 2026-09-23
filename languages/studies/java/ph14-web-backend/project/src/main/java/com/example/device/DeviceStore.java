// project/src/main/java/com/example/device/DeviceStore.java —— 内存设备数据存储
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（单元测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：本阶段项目聚焦 Web 层，数据层用内存 Map 模拟「数据访问接口」——
// 接口形状（save/findLatest/findHistory）与真实数据层一致，ph13 的 HikariCP+JDBC
// 实现可以直接替换进来（ph15 讲框架级数据访问）。并发用 ConcurrentHashMap +
// AtomicLong 保证线程安全（ph09 并发阶段的心智）。
package com.example.device;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/** 设备上报的线程安全内存存储（数据层接口的最小实现）。 */
@Component
public class DeviceStore {

    private final Map<String, List<DeviceReport>> byDeviceID = new ConcurrentHashMap<>();
    private final AtomicLong seq = new AtomicLong(1);

    /** 保存一条上报，返回带服务端分配 id 的记录。 */
    public DeviceReport save(String device_id, double lat, double lng, int speedKph, int componentPct, long reportedAt) {
        DeviceReport report = new DeviceReport(seq.getAndIncrement(), device_id, lat, lng, speedKph, componentPct, reportedAt);
        byDeviceID.computeIfAbsent(device_id, k -> new ArrayList<>()).add(report);
        return report;
    }

    /** 某台设备的最新一条上报（按上报时间最新；同秒内按 id 更大者最新）。 */
    public Optional<DeviceReport> findLatest(String device_id) {
        List<DeviceReport> list = byDeviceID.get(device_id);
        if (list == null || list.isEmpty()) return Optional.empty();
        return list.stream().max(Comparator
                .comparingLong(DeviceReport::reportedAt)
                .thenComparingLong(DeviceReport::id));
    }

    /** 某台设备的上报历史（按时间升序；limit 限制条数）。 */
    public List<DeviceReport> findHistory(String device_id, int limit) {
        List<DeviceReport> list = byDeviceID.get(device_id);
        if (list == null || list.isEmpty()) return List.of();
        List<DeviceReport> sorted = new ArrayList<>(list);
        sorted.sort(Comparator.comparingLong(DeviceReport::reportedAt));
        return sorted.subList(Math.max(0, sorted.size() - limit), sorted.size());
    }
}
