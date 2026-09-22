// project/src/main/java/com/example/vehicle/VehicleController.java —— 车辆数据上报 REST API
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试 + spring-boot:run + curl 实测，见 README）
// 实测结果（curl 直测，端口 18090）：
//   POST /api/vehicles/report {"vin":"LSVAB4BR0DA123456","lat":31.23,"lng":121.47,"speedKph":60,"batteryPct":88}
//     → 200 {"code":0,"message":"ok","data":{"id":1,"vin":"LSVAB4BR0DA123456","lat":31.23,...}}
//   POST 同上（VIN 非法 12 位）→ 400 {"code":40000,"message":"参数校验失败","data":{"vin":"VIN 必须为 17 位字母数字"}}
//   POST 同上（batteryPct=150）→ 400 {"code":40000,"message":"参数校验失败","data":{"batteryPct":"电量不能超过 100%"}}
//     （@Valid 先拦「输入形状」→ 40000；Service 层业务码 40001/40004 由 VehicleServiceTest 单测覆盖，见 README「校验双层实测」）
//   GET  /api/vehicles/LSVAB4BR0DA123456/status → 200 最新一条
//   GET  /api/vehicles/LSVAB4BR0DA123456/reports?limit=2 → 200 历史（按时间升序）
//   GET  /api/vehicles/NOTEXIST123456789/status → 404 {"code":40401,"message":"该车辆暂无上报数据"}
// ---------------------------------------------------------------------------
// 教学点：资源路径设计——车辆是资源（/api/vehicles/{vin}），状态/历史是子资源。
// @PathVariable 取路径参数、@RequestParam 取查询参数、@RequestBody 取 JSON 体；
// @Valid 触发 VehicleReportRequest 上的声明式校验（@NotBlank/@Pattern/@Min/@Max），
// 校验失败由全局异常处理器转 400（对比 Service 里的手工校验：Controller 校验「输入形状」、
// Service 校验「业务规则」，两层各司其职——与 ph13 数据库阶段的「Java 校验 + 数据库约束
// 分层兜底」同一思想）。
package com.example.vehicle;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/vehicles")
public class VehicleController {

    private final VehicleService service;

    public VehicleController(VehicleService service) {
        this.service = service;
    }

    /** 上报请求体：声明式校验「输入形状」。 */
    public record ReportRequest(
            @NotBlank(message = "VIN 不能为空")
            @Pattern(regexp = "^[A-HJ-NPR-Z0-9]{17}$", message = "VIN 必须为 17 位字母数字")
            String vin,
            @Min(value = -90, message = "纬度不能小于 -90")
            @Max(value = 90, message = "纬度不能大于 90")
            double lat,
            @Min(value = -180, message = "经度不能小于 -180")
            @Max(value = 180, message = "经度不能大于 180")
            double lng,
            @Min(value = 0, message = "车速不能为负")
            @Max(value = 300, message = "车速不能超过 300 km/h")
            int speedKph,
            @Min(value = 0, message = "电量不能为负")
            @Max(value = 100, message = "电量不能超过 100%")
            int batteryPct) {}

    /** 上报车辆数据。 */
    @PostMapping("/report")
    public ApiResponse<VehicleReport> report(@Valid @RequestBody ReportRequest req) {
        VehicleReport saved = service.report(req.vin(), req.lat(), req.lng(),
                req.speedKph(), req.batteryPct(), Instant.now().getEpochSecond());
        return ApiResponse.ok(saved);
    }

    /** 查询车辆最新状态。 */
    @GetMapping("/{vin}/status")
    public ApiResponse<VehicleReport> status(@PathVariable String vin) {
        VehicleReport latest = service.latest(vin)
                .orElseThrow(() -> new VehicleService.BusinessException("40401", "该车辆暂无上报数据"));
        return ApiResponse.ok(latest);
    }

    /** 查询车辆上报历史（?limit=N，默认 20，上限 100）。 */
    @GetMapping("/{vin}/reports")
    public ApiResponse<List<VehicleReport>> history(@PathVariable String vin,
                                                    @RequestParam(required = false) Integer limit) {
        return ApiResponse.ok(service.history(vin, limit));
    }
}
