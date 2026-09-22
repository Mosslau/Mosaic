// examples/ex01-node-management/NodeRepository.java —— 仓储接口(领域层只依赖接口)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
import java.util.Optional;

/** DDD：仓储只对聚合根操作，接口放在领域层、实现在基础设施层。 */
interface NodeRepository {
    Optional<SourceNode> findByVin(String sourceId);
    void save(SourceNode node);
    int count();
}
