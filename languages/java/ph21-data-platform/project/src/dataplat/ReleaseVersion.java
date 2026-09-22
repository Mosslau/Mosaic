// project/src/dataplat/ReleaseVersion.java —— 语义化版本
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
record ReleaseVersion(int major, int minor, int patch) implements Comparable<ReleaseVersion> {
    static ReleaseVersion of(String s) {
        String[] p = s.split("\\.");
        return new ReleaseVersion(Integer.parseInt(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2]));
    }
    @Override public int compareTo(ReleaseVersion o) {
        int c = Integer.compare(major, o.major);
        if (c != 0) { return c; }
        c = Integer.compare(minor, o.minor);
        return c != 0 ? c : Integer.compare(patch, o.patch);
    }
    @Override public String toString() { return major + "." + minor + "." + patch; }
}
