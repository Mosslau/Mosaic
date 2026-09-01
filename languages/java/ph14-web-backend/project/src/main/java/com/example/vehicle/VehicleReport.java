// project/src/main/java/com/example/vehicle/VehicleReport.java —— 车辆领域模型
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// ---------------------------------------------------------------------------
// 教学点：不可变 record 承载领域数据；经纬度用 double（坐标精度需求）、
// 电量/速度用 int（百分比/整数），金额类才必须 BigDecimal（见 ph03 常用类阶段）。
// 本类只做纯数据载体，不掺业务逻辑——业务规则放 VehicleService（Controller 不写业务）。
package com.example.vehicle;

/** 车辆一次上报的快照数据（不可变）。 */
public record VehicleReport(
        long id,          // 上报记录 id（服务端分配）
        String vin,       // 车辆识别码（17 位，唯一标识一辆车）
        double lat,       // 纬度
        double lng,       // 经度
        int speedKph,     // 车速 km/h
        int batteryPct,   // 电量百分比 0~100
        long reportedAt   // 上报时间戳（epoch 秒）
) {}
