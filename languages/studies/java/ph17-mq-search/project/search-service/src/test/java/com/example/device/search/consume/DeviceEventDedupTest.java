// 验证环境：OpenJDK 17 + Maven 3.9；测试命令：mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service test
// 验证状态：未在本环境验证
package com.example.device.search.consume;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** (sn,seq) 幂等去重：同设备同序号只放行一次、seq 回退丢弃（无需中间件，未在本环境验证） */
class DeviceEventDedupTest {

    private DeviceEventDedup dedup;

    @BeforeEach
    void setUp() {
        dedup = new DeviceEventDedup();
    }

    @Test
    void firstSequenceIsAccepted() {
        assertTrue(dedup.tryAccept("sn-001", 1), "新设备第一条应放行");
        assertEquals(1, dedup.acceptedCount());
    }

    @Test
    void duplicateDeliveryIsRejected() {
        dedup.tryAccept("sn-001", 5);
        assertFalse(dedup.tryAccept("sn-001", 5), "重复投递（同 seq）应被丢弃——at-least-once 的重复消费由此拦住");
        assertEquals(1, dedup.acceptedCount());
        assertEquals(1, dedup.rejectedCount());
    }

    @Test
    void staleLateSequenceIsRejected() {
        dedup.tryAccept("sn-001", 5);
        assertFalse(dedup.tryAccept("sn-001", 3), "seq 回退的迟到旧数据应被丢弃——不破坏单设备状态");
        dedup.tryAccept("sn-001", 6);
        assertEquals(2, dedup.acceptedCount(), "只有严格递增的 seq 放行");
    }

    @Test
    void devicesAreIsolated() {
        dedup.tryAccept("sn-001", 1);
        assertTrue(dedup.tryAccept("sn-002", 1), "不同设备各自独立计数，互不干扰");
        assertEquals(2, dedup.acceptedCount());
    }
}
