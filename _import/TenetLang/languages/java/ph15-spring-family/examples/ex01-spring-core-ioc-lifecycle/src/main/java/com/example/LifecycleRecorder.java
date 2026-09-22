package com.example;

import java.util.ArrayList;
import java.util.List;

/**
 * 生命周期事件记录器：把 Bean 各阶段回调追加进静态列表，供测试断言顺序。
 * 教学点：静态列表只用于「观察顺序」这一演示目的——生产代码禁止共享可变静态状态
 * （用 SLF4J 日志观察即可，见 ph15 主文档 3.2 节的 log 版本）。
 */
public final class LifecycleRecorder {

    /** 全容器共享的事件序列（每次测试前 clear） */
    public static final List<String> EVENTS = new ArrayList<>();

    private LifecycleRecorder() {
    }

    public static void record(String event) {
        EVENTS.add(event);
    }
}
