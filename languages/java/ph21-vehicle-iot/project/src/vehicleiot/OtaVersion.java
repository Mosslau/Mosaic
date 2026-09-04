// project/src/vehicleiot/OtaVersion.java —— 语义化固件版本
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
record OtaVersion(int major, int minor, int patch) implements Comparable<OtaVersion> {
    static OtaVersion of(String s) {
        String[] p = s.split("\\.");
        return new OtaVersion(Integer.parseInt(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2]));
    }
    @Override public int compareTo(OtaVersion o) {
        int c = Integer.compare(major, o.major);
        if (c != 0) { return c; }
        c = Integer.compare(minor, o.minor);
        return c != 0 ? c : Integer.compare(patch, o.patch);
    }
    @Override public String toString() { return major + "." + minor + "." + patch; }
}
