package com.example.caller;

/** 下游 5xx（可重试的失败类别之一） */
class Downstream5xxException extends RuntimeException {

    Downstream5xxException(int status) {
        super("downstream 5xx: " + status);
    }
}
