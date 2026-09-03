// project/src/seckill/SimClock.java —— 秒杀 demo 的虚拟时钟（时间全部走注入，演示可确定性断言）
// 教学映射：真实系统用 System.currentTimeMillis()/Redis PEXPIRE 的服务端时钟；本 demo 全部用
//           手动时钟驱动「锁租约到期」「缓存 TTL 到期」，保证多线程/时间相关断言结果确定可复现。
package seckill;

/** 时间源抽象 */
interface Clock {
    long now();
}

/** 手动时钟：demo 用它拨时间（生产不出现，只在测试/演示里推进） */
final class ManualClock implements Clock {
    private long t;

    ManualClock(long start) {
        this.t = start;
    }

    void advance(long ms) {
        t += ms;
    }

    @Override
    public long now() {
        return t;
    }
}
