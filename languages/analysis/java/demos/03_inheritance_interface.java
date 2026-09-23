// 03 · 单继承与接口：Java 的多态答案演示
// 运行：java demos/03_inheritance_interface.java
// 注意：单文件模式运行要求 main 所在类是第一个顶层类，故辅助类型都做成嵌套类

import java.util.ArrayList;
import java.util.List;

class InheritanceInterfaceDemo {

    // ---- 辅助类型全部嵌套于此（单文件模式要求 main 在第一个顶层类）----

    static class Device {
        private final String name;
        Device(String name) { this.name = name; }
        String describe() { return name + "（设备）"; }   // 子类可覆写（动态分派）
    }

    interface Electric { void charge(); }                 // 契约：能补能
    interface Navigable { void navigate(); }              // 契约：能导航

    static class Car extends Device implements Electric, Navigable {
        Car() { super("设备"); }
        @Override public void charge()   { System.out.println("   补能中……"); }
        @Override public void navigate() { System.out.println("   导航中……"); }
        @Override public String describe() { return super.describe() + " · Car"; }
    }

    // JDK 8 default 方法：给接口加方法不再破坏所有实现者
    interface Alarm {
        default void alarm() { System.out.println("   （默认告警声）哔——"); }
    }
    static class Car2 extends Device implements Electric, Navigable, Alarm {
        Car2() { super("设备"); }
        @Override public void charge()   { System.out.println("   快充中……"); }
        @Override public void navigate() { System.out.println("   越野导航中……"); }
        // alarm() 不实现也能用——default 兜底
    }

    // 面向契约编程：函数只认接口，不关心具体类
    static void goCharge(Electric e) { System.out.println("   [按 Electric 契约补能]"); e.charge(); }
    static void goNav(Navigable n)   { System.out.println("   [按 Navigable 契约导航]"); n.navigate(); }

    // ---- main ----
    public static void main(String[] args) {
        System.out.println("== 1. 单继承 + 多接口：一个对象多种身份 ==");
        Car car = new Car();
        System.out.println("   " + car.describe());            // 继承的方法（覆写后）
        goCharge(car);   // Car 是 Electric
        goNav(car);      // Car 是 Navigable

        System.out.println("\n== 2. 动态分派：父类引用调子类实现 ==");
        Device v = new Car();        // 引用类型是 Device，实际对象是 Car
        System.out.println("   v.describe() = " + v.describe() + "   ← 运行期查 vtable，调的是 Car 的覆写");

        System.out.println("\n== 3. default 方法：接口演进不破坏实现者 ==");
        Car2 suv = new Car2();
        suv.alarm();                   // 没实现 Alarm.alarm，用 default 兜底
        System.out.println("   Car2 无需改动即可获得新增的 alarm() 能力");

        System.out.println("\n== 4. 现实印证：List 是接口，实现随便换 ==");
        List<String> list = new ArrayList<>();   // 面向 List 契约编程
        list.add("A");
        System.out.println("   面向 List 接口的代码，换成 LinkedList 实现零改动");
        System.out.println("   → 这正是'继承少用、接口多用、组合默认'的生态证据");
    }
}
