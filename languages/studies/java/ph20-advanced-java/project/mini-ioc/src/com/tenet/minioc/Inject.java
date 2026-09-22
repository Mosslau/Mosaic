/*
 * project/mini-ioc/src/com/tenet/minioc/Inject.java
 * 注入点标记：放在「构造器」= 构造器注入（容器选它并解析参数）；
 * 放在「字段」= 字段注入（对象创建后容器反射赋值）。
 */
package com.tenet.minioc;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.CONSTRUCTOR, ElementType.FIELD})
public @interface Inject {
}
