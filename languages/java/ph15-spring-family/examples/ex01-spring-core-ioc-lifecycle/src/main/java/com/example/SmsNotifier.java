package com.example;

import org.springframework.stereotype.Component;

/** 短信通知器：Bean 名即类型名小写首字母 "smsNotifier"，需要它的注入点用 @Qualifier("smsNotifier") */
@Component("smsNotifier")
public class SmsNotifier implements Notifier {

    @Override
    public String channel() {
        return "sms";
    }
}
