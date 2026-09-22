// examples/ex01-device-management/VehicleDevice.java —— 车辆设备聚合根：身份 + 状态机 + 固件版本
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// DDD 教学点：状态机与「固件升级时必须 ONLINE/UPDATING」这类不变式收在聚合根内部，
// 应用服务不能直接改 status 字段——任何非法迁移在这里抛异常，而不是散落在 Service 里。
public final class VehicleDevice {
    private final String vin;          // 聚合根身份：车架号，全局唯一、不可变
    private final String model;        // 车型(配置信息，非身份)
    private DeviceStatus status;       // 当前状态(可变，受状态机约束)
    private String firmwareVersion;    // 当前固件版本(OTA 完成后提升)
    private long lastTelemetrySeq;     // 最近一次遥测序号(乱序保护，见 ex03 的 CHM 思路)

    public VehicleDevice(String vin, String model, String firmwareVersion) {
        this.vin = vin;
        this.model = model;
        this.firmwareVersion = firmwareVersion;
        this.status = DeviceStatus.REGISTERED;
    }

    /** 注册完成、正式入网。 */
    public DeviceEvent activate(String reason) {
        require(this.status == DeviceStatus.REGISTERED, "activate 只允许 REGISTERED 状态");
        return transition(DeviceStatus.ONLINE, reason);
    }

    /** 遥测上报：不仅推进状态，还按序号丢弃乱序旧帧(数据链路第一道闸)。 */
    public DeviceEvent onTelemetry(long seq, String reason) {
        if (seq <= this.lastTelemetrySeq) {
            return null;  // 乱序/重复帧：不推进状态也不产事件
        }
        this.lastTelemetrySeq = seq;
        DeviceStatus target = this.status == DeviceStatus.OFFLINE ? DeviceStatus.ONLINE : this.status;
        if (this.status == DeviceStatus.OFFLINE) {
            return transition(DeviceStatus.ONLINE, reason);
        }
        return null;      // 已 ONLINE/UPDATING 则仅刷新心跳序号
    }

    /** 心跳超时判离线。 */
    public DeviceEvent markOffline(String reason) {
        require(this.status == DeviceStatus.ONLINE, "markOffline 只允许 ONLINE 状态");
        return transition(DeviceStatus.OFFLINE, reason);
    }

    /** 进入 OTA：只有 ONLINE/OFFLINE 能升级；升级中拒绝其它指令。 */
    public DeviceEvent startOta(String reason) {
        require(this.status == DeviceStatus.ONLINE || this.status == DeviceStatus.OFFLINE,
                "startOta 只允许 ONLINE/OFFLINE 状态");
        return transition(DeviceStatus.UPDATING, reason);
    }

    /** OTA 成功：固件版本升级并回到 ONLINE。 */
    public DeviceEvent finishOta(String newFirmware, String reason) {
        require(this.status == DeviceStatus.UPDATING, "finishOta 只允许 UPDATING 状态");
        this.firmwareVersion = newFirmware;
        return transition(DeviceStatus.ONLINE, reason);
    }

    /** OTA 失败：保持原固件回到 ONLINE(回滚在 OTA 平台侧做，见 ex06)。 */
    public DeviceEvent failOta(String reason) {
        require(this.status == DeviceStatus.UPDATING, "failOta 只允许 UPDATING 状态");
        return transition(DeviceStatus.ONLINE, reason);
    }

    /** 报废退网：终态，不可再迁移。 */
    public DeviceEvent retire(String reason) {
        require(this.status != DeviceStatus.RETIRED, "RETIRED 是终态");
        return transition(DeviceStatus.RETIRED, reason);
    }

    private DeviceEvent transition(DeviceStatus to, String reason) {
        DeviceEvent event = DeviceEvent.of(this.vin, this.status, to, reason);
        this.status = to;
        return event;
    }

    private static void require(boolean ok, String msg) {
        if (!ok) {
            throw new IllegalStateException("非法状态迁移: " + msg);
        }
    }

    // ---- 只读访问器(无 setter，状态只能经上面的领域方法改变) ----
    public String vin()                { return this.vin; }
    public String model()              { return this.model; }
    public DeviceStatus status()       { return this.status; }
    public String firmwareVersion()    { return this.firmwareVersion; }
    public long lastTelemetrySeq()     { return this.lastTelemetrySeq; }
}
