package com.example.ordersaga;

import org.springframework.stereotype.Component;

/**
 * 物流预约（Saga 第 2 步的下游）。示例规则：item=fragile（易碎品）无可用运力 → 预约失败，
 * 用于稳定复现「扣款成功、后续步骤失败 → 必须补偿」的场景。真实系统里这是另一个远程服务。
 */
@Component
public class LogisticsService {

    public void reserve(String item) {
        if ("fragile".equals(item)) {
            throw new IllegalStateException("易碎品无可用运力，预约物流失败");
        }
    }
}
