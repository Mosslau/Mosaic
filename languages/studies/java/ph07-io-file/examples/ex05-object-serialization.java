// examples/ex05-object-serialization.java —— 对象序列化与反序列化：Serializable + transient + serialVersionUID
// 对应主文档「6. 代码示例 / 示例 5」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex05-object-serialization.java
// 运行：java ObjectSerialization
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;

class ObjectSerialization {
    // 必须实现 Serializable；显式声明版本号，防止类结构变化后无法反序列化
    static class User implements Serializable {
        private static final long serialVersionUID = 1L;
        String name;
        int age;
        transient String password;    // 敏感字段不落盘

        User(String name, int age, String password) {
            this.name = name;
            this.age = age;
            this.password = password;
        }

        @Override
        public String toString() {
            return "User{name='" + name + "', age=" + age
                    + ", password='" + password + "'}";
        }
    }

    public static void main(String[] args) {
        String file = "user.ser";
        try {
            // 序列化：对象 -> 字节流
            try (ObjectOutputStream out = new ObjectOutputStream(
                    new FileOutputStream(file))) {
                out.writeObject(new User("Alice", 20, "secret"));
            }
            // 反序列化：字节流 -> 对象
            try (ObjectInputStream in = new ObjectInputStream(
                    new FileInputStream(file))) {
                User u = (User) in.readObject();
                System.out.println("恢复: " + u);   // password 为 null
            }
            new File(file).delete();
        } catch (IOException | ClassNotFoundException e) {
            System.err.println("序列化失败: " + e.getMessage());
        }
    }
}
