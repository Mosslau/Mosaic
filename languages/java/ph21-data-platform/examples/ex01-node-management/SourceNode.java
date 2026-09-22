// examples/ex01-node-management/SourceNode.java —— 数据源节点聚合根：身份 + 状态机 + FW 版本版本
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// DDD 教学点：状态机与「FW 版本升级时必须 ONLINE/UPDATING」这类不变式收在聚合根内部，
// 应用服务不能直接改 status 字段——任何非法迁移在这里抛异常，而不是散落在 Service 里。
public final class SourceNode {
    private final String sourceId;          // 聚合根身份：g架号，全局唯一、不可变
    private final String model;        // 数据源类型(配置信息，非身份)
    private NodeStatus status;       // 当前状态(可变，受状态机约束)
    private String firmwareVersion;    // 当前FW 版本版本(版本发布 完成后提升)
    private long lastTelemetrySeq;     // 最近一次指标序号(乱序保护，见 ex03 的 CHM 思路)

    public SourceNode(String sourceId, String model, String firmwareVersion) {
        this.sourceId = sourceId;
        this.model = model;
        this.firmwareVersion = firmwareVersion;
        this.status = NodeStatus.REGISTERED;
    }

    /** 注册完成、正式入网。 */
    public NodeEvent activate(String reason) {
        require(this.status == NodeStatus.REGISTERED, "activate 只允许 REGISTERED 状态");
        return transition(NodeStatus.ONLINE, reason);
    }

    /** 指标上报：不仅推进状态，还按序号丢弃乱序旧帧(数据链路第一道闸)。 */
    public NodeEvent onTelemetry(long seq, String reason) {
        if (seq <= this.lastTelemetrySeq) {
            return null;  // 乱序/重复帧：不推进状态也不产事件
        }
        this.lastTelemetrySeq = seq;
        NodeStatus target = this.status == NodeStatus.OFFLINE ? NodeStatus.ONLINE : this.status;
        if (this.status == NodeStatus.OFFLINE) {
            return transition(NodeStatus.ONLINE, reason);
        }
        return null;      // 已 ONLINE/UPDATING 则仅刷新心跳序号
    }

    /** 心跳超时判离线。 */
    public NodeEvent markOffline(String reason) {
        require(this.status == NodeStatus.ONLINE, "markOffline 只允许 ONLINE 状态");
        return transition(NodeStatus.OFFLINE, reason);
    }

    /** 进入 版本发布：只有 ONLINE/OFFLINE 能升级；升级中拒绝其它指令。 */
    public NodeEvent startOta(String reason) {
        require(this.status == NodeStatus.ONLINE || this.status == NodeStatus.OFFLINE,
                "startOta 只允许 ONLINE/OFFLINE 状态");
        return transition(NodeStatus.UPDATING, reason);
    }

    /** 版本发布 成功：FW 版本版本升级并回到 ONLINE。 */
    public NodeEvent finishOta(String newFirmware, String reason) {
        require(this.status == NodeStatus.UPDATING, "finishOta 只允许 UPDATING 状态");
        this.firmwareVersion = newFirmware;
        return transition(NodeStatus.ONLINE, reason);
    }

    /** 版本发布 失败：保持原FW 版本回到 ONLINE(回滚在 版本发布 平台侧做，见 ex06)。 */
    public NodeEvent failOta(String reason) {
        require(this.status == NodeStatus.UPDATING, "failOta 只允许 UPDATING 状态");
        return transition(NodeStatus.ONLINE, reason);
    }

    /** 报废退网：终态，不可再迁移。 */
    public NodeEvent retire(String reason) {
        require(this.status != NodeStatus.RETIRED, "RETIRED 是终态");
        return transition(NodeStatus.RETIRED, reason);
    }

    private NodeEvent transition(NodeStatus to, String reason) {
        NodeEvent event = NodeEvent.of(this.sourceId, this.status, to, reason);
        this.status = to;
        return event;
    }

    private static void require(boolean ok, String msg) {
        if (!ok) {
            throw new IllegalStateException("非法状态迁移: " + msg);
        }
    }

    // ---- 只读访问器(无 setter，状态只能经上面的领域方法改变) ----
    public String sourceId()                { return this.sourceId; }
    public String model()              { return this.model; }
    public NodeStatus status()       { return this.status; }
    public String firmwareVersion()    { return this.firmwareVersion; }
    public long lastTelemetrySeq()     { return this.lastTelemetrySeq; }
}
