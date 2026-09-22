package com.example;

import java.util.ArrayList;
import java.util.List;

/** 请求处理阶段记录器：Filter/拦截器/Controller 把「我此刻执行了」追加进来，测试断言执行顺序（静态列表仅用于观察演示） */
public final class OrderRecorder {

    public static final List<String> FLOW = new ArrayList<>();

    private OrderRecorder() {
    }

    public static void record(String event) {
        FLOW.add(event);
    }
}
