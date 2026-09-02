package com.example;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

/**
 * 注入点演示：构造器注入 + @Qualifier 精确点名。
 * 注意本类没有 @Primary 依赖——它要的是 sms 那一个，不是「默认那个」。
 */
@Service
public class AlertService {

    private final Notifier notifier;

    public AlertService(@Qualifier("smsNotifier") Notifier notifier) {
        this.notifier = notifier;
    }

    public String channel() {
        return notifier.channel();
    }
}
