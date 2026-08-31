// examples/ex02-jar-manifest.java —— jar 打包与清单演示：Main-Class、java -jar、ufe 事后补主类
// 验证环境：OpenJDK 17.0.18（jar/unzip 为 JDK/系统自带）
// 验证状态：已验证（本机实测, 关键输出见下）
// 编译/运行命令：
//   1. 编译（单文件、默认包）
//      javac -d build ex02-jar-manifest.java
//   2. 先打一个没有 Main-Class 的 jar——java -jar 必然失败
//      jar cf app-plain.jar -C build .
//      java -jar app-plain.jar          # 实测报错: app-plain.jar中没有主清单属性
//   3. 用 cfe 打带入口类的 jar（cfe = create file with entrypoint）
//      jar cfe app-main.jar JarManifestDemo -C build .
//      java -jar app-main.jar           # 实测输出: hello from jar
//   4. ufe 事后给普通 jar 补主类（ufe = update file with entrypoint）
//      jar ufe app-plain.jar JarManifestDemo -C build .
//      java -jar app-plain.jar          # 实测输出: hello from jar
//   5. 查看清单：unzip -p app-main.jar META-INF/MANIFEST.MF  →  Main-Class: JarManifestDemo
//   6. 产物清理：rm -rf build app-plain.jar app-main.jar
// 说明：jar 本质是 zip + META-INF/MANIFEST.MF 清单; java -jar 只认清单里的 Main-Class。
//       类为默认包且非 public（public 类必须与文件名同名, 此处刻意用 ex0X-*.java 命名）。
class JarManifestDemo {
    public static void main(String[] args) {
        System.out.println("hello from jar");
    }
}
