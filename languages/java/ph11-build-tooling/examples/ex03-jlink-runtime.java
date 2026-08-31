// examples/ex03-jlink-runtime.java —— jlink 精简运行时演示：jdeps 分析 + jlink 裁剪 + 体积对比
// 验证环境：OpenJDK 17.0.18（jdeps/jlink 为 JDK 自带）
// 验证状态：已验证（本机实测, 数字见下）
// 编译/运行命令：
//   1. 编译
//      javac -d build ex03-jlink-runtime.java
//   2. 分析程序依赖哪些 JDK 模块（本机实测输出: java.base,java.logging）
//      jdeps --print-module-deps build/JlinkRuntimeDemo.class
//   3. 只带这两个模块裁剪一个最小运行时（默认输出目录名 runtime-min, 勿与源码目录混放）
//      jlink --add-modules java.base,java.logging --output runtime-min
//   4. 用精简运行时运行（本机实测输出: hello from jlink runtime; LOG.info 输出走 stderr）
//      runtime-min/bin/java -cp build JlinkRuntimeDemo
//   5. 体积对比（本机实测, 随 JDK 安装位置不同数字略有差异）
//      du -sh runtime-min        # 41M
//      du -sh <JDK 根目录>        # 305M（完整 JDK）——裁掉约 87%
//   6. 演示缺模块的后果：只加 java.base 运行时, 用到 java.logging 就崩
//      jlink --add-modules java.base --output runtime-base
//      runtime-base/bin/java -cp build JlinkRuntimeDemo   # 实测 NoClassDefFoundError: java/util/logging/Logger
//   7. 产物清理：rm -rf build runtime-min runtime-base
// 说明：jlink 按「模块」裁剪 JDK 镜像, 而不是按类裁剪; jdeps 帮你找出程序用到的模块闭包。
import java.util.logging.Logger;

class JlinkRuntimeDemo {
    private static final Logger LOG = Logger.getLogger(JlinkRuntimeDemo.class.getName());

    public static void main(String[] args) {
        LOG.info("jlink demo started");
        System.out.println("hello from jlink runtime");
        LOG.info("args count = " + args.length);
    }
}
