// examples/ex04-generic-repository.java —— 泛型 Repository：泛型接口 + 实现类绑定具体类型
// 对应主文档「6. 代码示例 / 示例 4」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex04-generic-repository.java
// 运行：java GenericRepository
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.*;

class GenericRepository {
    // 泛型接口：定义数据访问契约，与具体实体类型无关
    interface Repository<T> {
        void save(T entity);
        Optional<T> findById(String id);
        List<T> findAll();
        void deleteById(String id);
    }

    static class User {
        String id, name;

        User(String i, String n) { id = i; name = n; }
        public String toString() { return "User{id=" + id + ", name=" + name + "}"; }
    }

    // 实现时绑定具体类型：UserRepository 只处理 User
    static class UserRepository implements Repository<User> {
        private final Map<String, User> store = new HashMap<>();

        public void save(User u) { store.put(u.id, u); }
        public Optional<User> findById(String id) { return Optional.ofNullable(store.get(id)); }
        public List<User> findAll() { return new ArrayList<>(store.values()); }
        public void deleteById(String id) { store.remove(id); }
    }

    public static void main(String[] args) {
        Repository<User> repo = new UserRepository();
        repo.save(new User("u1", "Alice"));
        repo.save(new User("u2", "Bob"));
        System.out.println("全部用户: " + repo.findAll());
        System.out.println("查找 u2: " + repo.findById("u2").orElse(null));
        repo.deleteById("u1");
        System.out.println("删除后: " + repo.findAll());
    }
}
