// project/src/lakeplat/Layer.java —— 数仓四层：层级序号即依赖方向纪律
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 分层建模的四层（主文档 3.1）。
 *
 * <p>枚举的 {@link #ordinal()} 就是层级序号：数据只允许从**上游**（序号小）流向下游（序号大）。
 * 把这个纪律写成枚举而不是注释，是为了让「DWD 直接读 ADS」这种反向依赖在**建模阶段**就被拒绝，
 * 而不是等对账时才发现两个数对不上。
 */
public enum Layer {
    /** 原始层：贴着源系统落原始数据，不做业务解释，只做格式校验。 */
    ODS("原始层", "全量字段、含脏数据（只做格式校验）"),
    /** 明细层：清洗、去重、维度退化后的明细事实，一条业务事件一行。 */
    DWD("明细层", "已清洗、一实体一行/一事件一行"),
    /** 汇总层：按主题聚合的轻度汇总；**指标口径的唯一源**。 */
    DWS("汇总层", "由 DWD 聚合而来，可回溯到明细"),
    /** 应用层：面向具体看板/接口的结果集，只做展示态加工。 */
    ADS("应用层", "由 DWS 或 DWD 聚合，可被整体替换重算");

    private final String cnName;
    private final String dataShape;

    Layer(String cnName, String dataShape) {
        this.cnName = cnName;
        this.dataShape = dataShape;
    }

    /** 中文层名（用于一屏与可读报错）。 */
    public String cnName() {
        return cnName;
    }

    /** 该层允许的数据形态（主文档 3.1 表格的第三列）。 */
    public String dataShape() {
        return dataShape;
    }

    /** 是否允许 {@code this} 读取 {@code upstream}：只有上游层（序号更小或相同）可被读取。 */
    public boolean canReadFrom(Layer upstream) {
        return upstream.ordinal() <= this.ordinal();
    }

    /** 层间箭头（一屏与 README 用）：`ODS → DWD`。 */
    public String arrowTo(Layer downstream) {
        return name() + " → " + downstream.name();
    }
}
