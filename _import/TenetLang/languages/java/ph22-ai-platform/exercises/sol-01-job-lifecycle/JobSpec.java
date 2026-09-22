// exercises/sol-01-job-lifecycle/JobSpec.java —— 任务不可变定义 + 幂等键组成（specHash）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/**
 * 一次提交产生的不可变定义：提交后不允许修改，改动内容就是一次新提交（specHash 随之改变）。
 */
public record JobSpec(String tenant, String name, int gpus, String image) {

    public JobSpec {
        if (tenant == null || tenant.isBlank()) {
            throw new IllegalArgumentException("租户不能为空");
        }
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("任务名不能为空");
        }
        if (gpus <= 0) {
            throw new IllegalArgumentException("GPU 数量必须为正数：" + gpus);
        }
        if (image == null || image.isBlank()) {
            throw new IllegalArgumentException("镜像不能为空");
        }
    }

    /**
     * 定义的确定性指纹（不依赖 JVM 运行，同内容必得同值）。
     * 幂等键 = tenant + name + specHash：改了卡数或镜像就是另一个任务。
     */
    public String specHash() {
        int h = 17;
        h = 31 * h + tenant.hashCode();
        h = 31 * h + name.hashCode();
        h = 31 * h + gpus;
        h = 31 * h + image.hashCode();
        return String.format("%08x", h);
    }
}
