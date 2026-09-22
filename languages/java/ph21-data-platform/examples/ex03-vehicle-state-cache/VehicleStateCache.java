// examples/ex03-vehicle-state-cache/VehicleStateCache.java —— 实时状态缓存(CHM + computeIfPresent 原子读改写)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点(兑现 ph20 CHM 预告)：实时状态缓存是「先 get 再 put」的高发场景——两路网关并发上报同一 VIN 时，
// 先读旧值再写新值会丢更新。正确做法是把「读旧→比较 seq→写新」整段塞进 computeIfPresent，
// 由 CHM 桶锁保证原子。get 走无锁读：读到旧快照可接受(弱一致)，但绝不读到半写状态。
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

public final class VehicleStateCache {
    private final ConcurrentHashMap<String, VehicleState> states = new ConcurrentHashMap<>();
    private final LongAdder staleDropped = new LongAdder();   // 乱序旧帧丢弃计数(数据质量可观测)

    /** 原子写：仅当新帧序号更大才替换。返回是否被采纳。 */
    public boolean update(VehicleState incoming) {
        boolean[] replaced = {false};
        // 一次 compute 覆盖「首次出现」与「已存在」两种情况：桶锁内读-比-写整段原子，
        // 不存在「先 get 再 put」的竞态窗口；soc 复用 seq 单调性做乱序保护。
        states.compute(incoming.vin(), (vin, current) -> {
            if (current == null || incoming.seq() > current.seq()) {
                replaced[0] = true;                 // 新帧更新(或首帧)
                return incoming;
            }
            staleDropped.increment();               // 乱序/重复：丢弃并计数
            return current;
        });
        return replaced[0];
    }

    /** 无锁读：弱一致但安全(拿到的快照要么旧要么新，不会半写)。 */
    public VehicleState get(String vin) {
        return states.get(vin);
    }

    /** 全量快照(弱一致遍历，并发更新时部分新部分旧——可接受)。 */
    public List<VehicleState> snapshot() {
        return states.values().stream().sorted((a, b) -> a.vin().compareTo(b.vin())).toList();
    }

    public long staleDropped() { return staleDropped.sum(); }
    public int size()          { return states.size(); }
}
