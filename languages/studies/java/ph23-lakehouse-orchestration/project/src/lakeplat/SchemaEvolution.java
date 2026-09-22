// project/src/lakeplat/SchemaEvolution.java —— schema 演进兼容性校验：提交阶段的 fail-fast
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * schema 演进兼容性（主文档 3.2）。
 *
 * <p>规则只有两条：
 * <ul>
 *   <li><b>加列</b>（旧列全部保留、只多出新列）→ 兼容，旧数据该列为 null；</li>
 *   <li><b>删列 / 改类型</b> → 不兼容，历史文件读不出、下游类型断言全崩，必须在**提交阶段**拒绝。</li>
 * </ul>
 *
 * <p>为什么必须 fail-fast：若允许静默通过，错误会推迟到下游任务运行时才炸，而那时坏数据可能已经被写进 ADS。
 * 报错要给出「哪个列、什么变更、为什么不兼容」——这是变更评审能直接用的信息。
 */
public final class SchemaEvolution {

    private SchemaEvolution() {
    }

    /** 一次不兼容变更的可读描述。 */
    public record Violation(String column, String change, String reason) {
        @Override
        public String toString() {
            return "列 " + column + " " + change + "：" + reason;
        }
    }

    /** 兼容性判定：返回不兼容项列表，空表示兼容。 */
    public static List<Violation> violations(Schema from, Schema to) {
        List<Violation> violations = new ArrayList<>();
        Set<String> added = new LinkedHashSet<>(to.columns().keySet());
        added.removeAll(from.columns().keySet());
        for (String column : from.names()) {
            String oldType = from.columns().get(column);
            if (!to.has(column)) {
                if (added.contains(column)) {
                    violations.add(new Violation(column, "类型变更 " + oldType + " → " + to.columns().get(column),
                            "同一提交内既是删列又是加列，语义有歧义，必须拆成两次提交并显式确认"));
                } else {
                    violations.add(new Violation(column, "删除",
                            "删列后历史文件读不出该列，下游类型断言会崩（DROP COLUMN 需显式确认）"));
                }
                continue;
            }
            String newType = to.columns().get(column);
            if (!oldType.equals(newType)) {
                violations.add(new Violation(column, "类型变更 " + oldType + " → " + newType,
                        "改类型后历史文件按旧类型编码，读取会得到错值或直接失败（需显式确认）"));
            }
        }
        return List.copyOf(violations);
    }

    /** 兼容则返回；不兼容抛 {@link IllegalStateException}，错误信息可读。 */
    public static void check(Schema from, Schema to) {
        List<Violation> violations = violations(from, to);
        if (!violations.isEmpty()) {
            throw new IllegalStateException("schema 变更不兼容，提交被拒：" + violations
                    + "（兼容变更只有「加列」；删列/改类型需显式确认）");
        }
    }
}
