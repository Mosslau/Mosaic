/*
 * project/mini-ioc/src/com/tenet/minioc/Component.java
 * 标记「这是一个可被容器管理的组件」，可用 value 指定 bean 名，缺省用简单类名首字母小写。
 */
package com.tenet.minioc;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.TYPE)
public @interface Component {
    String value() default "";
}
