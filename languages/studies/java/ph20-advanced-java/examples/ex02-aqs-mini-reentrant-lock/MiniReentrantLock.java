/*
 * examples/ex02-aqs-mini-reentrant-lock/MiniReentrantLock.java + MiniReentrantLockDemo.java
 * 用 AbstractQueuedSynchronizer（AQS）自己实现一把「不可打断、非公平、可重入」互斥锁：
 * 只需覆写 tryAcquire/tryRelease 两个方法，AQS 提供 state + CLH 等待队列 + 阻塞/唤醒。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）/opt/homebrew/opt/openjdk@17
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls MiniReentrantLock.java MiniReentrantLockDemo.java
 * 运行：java -cp /tmp/tl20-cls MiniReentrantLockDemo
 * 本机已实测：输出 8 行 PASS（重入计数/互斥计数/超时返回 false）
 */
import java.util.concurrent.locks.AbstractQueuedSynchronizer;

/** 最小 AQS 互斥锁：state = 重入次数；0 空闲，>0 表示被 owner 持有并重入 n 次。 */
public final class MiniReentrantLock {
    private final Sync sync = new Sync();

    private static final class Sync extends AbstractQueuedSynchronizer {
        @Override
        protected boolean tryAcquire(int acquires) {       // AQS.acquire 的模板回调
            Thread current = Thread.currentThread();
            int c = getState();
            if (c == 0) {                                   // 空闲：CAS 抢锁
                if (compareAndSetState(0, acquires)) {
                    setExclusiveOwnerThread(current);       // 记录 owner（重入判断依据）
                    return true;
                }
            } else if (current == getExclusiveOwnerThread()) {
                int next = c + acquires;                    // 自己已持有 → state 累加 = 重入
                if (next < 0) {
                    throw new Error("maximum lock count exceeded");
                }
                setState(next);
                return true;
            }
            return false;                                   // 失败 → AQS 会把它放进 CLH 队列并 park
        }

        @Override
        protected boolean tryRelease(int releases) {
            int c = getState() - releases;
            if (Thread.currentThread() != getExclusiveOwnerThread()) {
                throw new IllegalMonitorStateException();   // 非持有者释放 = 程序错误
            }
            boolean free = false;
            if (c == 0) {                                   // 归零才真正释放
                free = true;
                setExclusiveOwnerThread(null);
            }
            setState(c);
            return free;                                    // true → AQS 唤醒队首后继
        }

        @Override
        protected boolean isHeldExclusively() {
            return getState() != 0 && getExclusiveOwnerThread() == Thread.currentThread();
        }
    }

    public void lock() {
        sync.acquire(1);
    }

    public void unlock() {
        sync.release(1);
    }

    /** 演示用：当前线程是否独占持有 */
    public boolean isHeldByCurrentThread() {
        return sync.isHeldExclusively();
    }
}
