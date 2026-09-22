// languages/java/ph23-lakehouse-orchestration/examples/ex01-warehouse-layers/Layer.java —— 数仓四层：序号即层级，依赖只能从低序号流向高序号
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex01 *.java && java -cp /tmp/ph23-ex01 WarehouseLayersDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么用 enum 而不是字符串常量：层级顺序本身就是「依赖方向纪律」的判据（上游 ordinal <= 下游），
// 用 enum 让这条纪律由类型系统承载——层级名写错在编译期就报错，而不是等运行期比对字符串才发现。
public enum Layer {

    /** 原始层：贴着源系统落原始数据，不做业务解释（清洗规则会变，变了要能从原始重算）。 */
    ODS,

    /** 明细层：清洗、去重、维度退化后的一条业务事件。 */
    DWD,

    /** 汇总层：按主题聚合的轻度汇总，也是「口径唯一源」——指标口径只允许在这一层定义。 */
    DWS,

    /** 应用层：面向看板/接口的结果集，只做展示态加工，可被整体替换重算。 */
    ADS;

    /** 是否为口径定义层：只有 DWS 可以定义口径列。 */
    public boolean isMetricLayer() {
        return this == DWS;
    }
}
