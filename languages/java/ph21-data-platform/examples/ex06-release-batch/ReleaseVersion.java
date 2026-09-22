// examples/ex06-ota-batch/ReleaseVersion.java —— 语义化FW 版本版本号(值对象)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Objects;

/** 版本比较必须语义化：字符串 "2.10" 会排在 "2.9" 前，语义化则相反——版本发布 选版全靠它。 */
record ReleaseVersion(int major, int minor, int patch) implements Comparable<ReleaseVersion> {
    static ReleaseVersion of(String s) {
        String[] p = s.split("\\.");
        return new ReleaseVersion(Integer.parseInt(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2]));
    }

    @Override public int compareTo(ReleaseVersion o) {
        int c = Integer.compare(major, o.major);
        if (c != 0) return c;
        c = Integer.compare(minor, o.minor);
        return c != 0 ? c : Integer.compare(patch, o.patch);
    }

    @Override public String toString() { return major + "." + minor + "." + patch; }
}
