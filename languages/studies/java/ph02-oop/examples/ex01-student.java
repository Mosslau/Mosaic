// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 1
// 说明：封装与学生类——字段 private，构造初始化，setter 校验不变量，重写 toString
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex01-student.java
// 运行：java StudentDemo
// 验证状态：已验证：OpenJDK 17.0.16
class StudentDemo {
    public static void main(String[] args) {
        Student s = new Student("Alice", 20);
        s.setAge(21);
        System.out.println(s);

        try {
            s.setAge(200);  // 触发 setter 校验
        } catch (IllegalArgumentException e) {
            System.out.println("校验拦截: " + e.getMessage());
        }
    }
}

class Student {
    private String name;
    private int age;

    Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() { return name; }
    public int getAge() { return age; }

    public void setAge(int age) {
        if (age < 0 || age > 150) {
            throw new IllegalArgumentException("年龄不合法: " + age);
        }
        this.age = age;
    }

    @Override
    public String toString() {
        return "Student{name='" + name + "', age=" + age + "}";
    }
}
