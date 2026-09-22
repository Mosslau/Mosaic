// examples/ex01-node-management/NodeStatus.java —— 节点生命周期状态机(聚合根内部状态)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
// 状态迁移合法性由 SourceNode 的方法保证，本枚举只定义状态集。
enum NodeStatus {
    REGISTERED,   // 刚出厂/刚注册：仅有档案，未连上平台
    ONLINE,       // 与接入网关保持长连接或最近心跳在阈值内
    OFFLINE,      // 掉线：心跳超时或主动断开
    UPDATING,     // 版本发布升级进行中(业务上拒绝下发其它指令)
    RETIRED       // 已报废/退网：只读档案，不再接收指标
}
