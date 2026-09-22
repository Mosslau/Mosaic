package com.example;

import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Component;

/** 邮件通知器：标 @Primary —— 同类型多 Bean 时默认注入它 */
@Component
@Primary
public class EmailNotifier implements Notifier {

    @Override
    public String channel() {
        return "email";
    }
}
