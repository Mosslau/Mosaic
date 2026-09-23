// project/src/main/java/com/example/device/DeviceController.java —— 设备数据上报 REST API
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试 + spring-boot:run + curl 实测，见 README）
// 实测结果（curl 直测，端口 18090）：
//   POST /api/devices/report {"device_id":"LSVAB4BR0DA123456","lat":31.23,"lng":121.47,"speedKph":60,"componentPct":88}
//     → 200 {"code":0,"message":"ok","data":{"id":1,"device_id":"LSVAB4BR0DA123456","lat":31.23,...}}
//   POST 同上（DEVICE_ID 非法 12 位）→ 400 {"code":40000,"message":"参数校验失败","data":{"device_id":"DEVICE_ID 必须为 17 位字母数字"}}
//   POST 同上（componentPct=150）→ 400 {"code":40000,"message":"参数校验失败","data":{"componentPct":"电量不能超过 100%"}}
//     （@Valid 先拦「输入形状」→ 40000；Service 层业务码 40001/40004 由 DeviceServiceTest 单测覆盖，见 README「校验双层实测」）
//   GET  /api/devices/LSVAB4BR0DA123456/status → 200 最新一条
//   GET  /api/devices/LSVAB4BR0DA123456/reports?limit=2 → 200 历史（按时间升序）
//   GET  /api/devices/NOTEXIST123456789/status → 404 {"code":40401,"message":"该设备暂无上报数据"}
// ---------------------------------------------------------------------------
// 教学点：资源路径设计——设备是资源（/api/devices/{device_id}），状态/历史是子资源。
// @PathVariable 取路径参数、@RequestParam 取查询参数、@RequestBody 取 JSON 体；
// @Valid 触发 DeviceReportRequest 上的声明式校验（@NotBlank/@Pattern/@Min/@Max），
// 校验失败由全局异常处理器转 400（对比 Service 里的手工校验：Controller 校验「输入形状」、
// Service 校验「业务规则」，两层各司其职——与 ph13 数据库阶段的「Java 校验 + 数据库约束
// 分层兜底」同一思想）。
package com.example.device;

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
@RequestMapping("/api/devices")
public class DeviceController {

    private final DeviceService service;

    public DeviceController(DeviceService service) {
        this.service = service;
    }

    /** 上报请求体：声明式校验「输入形状」。 */
    public record ReportRequest(
            @NotBlank(message = "DEVICE_ID 不能为空")
            @Pattern(regexp = "^[A-HJ-NPR-Z0-9]{17}$", message = "DEVICE_ID 必须为 17 位字母数字")
            String device_id,
            @Min(value = -90, message = "纬度不能小于 -90")
            @Max(value = 90, message = "纬度不能大于 90")
            double lat,
            @Min(value = -180, message = "经度不能小于 -180")
            @Max(value = 180, message = "经度不能大于 180")
            double lng,
            @Min(value = 0, message = "运行速度不能为负")
            @Max(value = 300, message = "运行速度不能超过 300 km/h")
            int speedKph,
            @Min(value = 0, message = "电量不能为负")
            @Max(value = 100, message = "电量不能超过 100%")
            int componentPct) {}

    /** 上报设备数据。 */
    @PostMapping("/report")
    public ApiResponse<DeviceReport> report(@Valid @RequestBody ReportRequest req) {
        DeviceReport saved = service.report(req.device_id(), req.lat(), req.lng(),
                req.speedKph(), req.componentPct(), Instant.now().getEpochSecond());
        return ApiResponse.ok(saved);
    }

    /** 查询设备最新状态。 */
    @GetMapping("/{device_id}/status")
    public ApiResponse<DeviceReport> status(@PathVariable String device_id) {
        DeviceReport latest = service.latest(device_id)
                .orElseThrow(() -> new DeviceService.BusinessException("40401", "该设备暂无上报数据"));
        return ApiResponse.ok(latest);
    }

    /** 查询设备上报历史（?limit=N，默认 20，上限 100）。 */
    @GetMapping("/{device_id}/reports")
    public ApiResponse<List<DeviceReport>> history(@PathVariable String device_id,
                                                    @RequestParam(required = false) Integer limit) {
        return ApiResponse.ok(service.history(device_id, limit));
    }
}
