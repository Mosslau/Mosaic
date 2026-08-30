// exercises/sol-04-generic-repository.java —— 练习 4 泛型 Repository 参考实现
// 泛型接口 Repository<T, ID> + 泛型基类 AbstractRepository 复用存储逻辑，两个实体各绑定具体类型
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-04-generic-repository.java
// 运行：java GenericRepositorySol
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.*;

class GenericRepositorySol {
    // 泛型接口：T 是实体类型，ID 是主键类型——比固定 String 主键更通用
    interface Repository<T, ID> {
        void save(T entity);
        Optional<T> findById(ID id);
        List<T> findAll();
        void deleteById(ID id);
        long count();
    }

    // 泛型抽象基类：把"如何取实体主键"留给子类，其余 CRUD 全部复用
    static abstract class AbstractRepository<T, ID> implements Repository<T, ID> {
        protected final Map<ID, T> store = new HashMap<>();

        // 子类实现：给定实体返回其主键
        protected abstract ID idOf(T entity);

        public void save(T entity) { store.put(idOf(entity), entity); }
        public Optional<T> findById(ID id) { return Optional.ofNullable(store.get(id)); }
        public List<T> findAll() { return new ArrayList<>(store.values()); }
        public void deleteById(ID id) { store.remove(id); }
        public long count() { return store.size(); }
    }

    static class User {
        final String id;
        final String name;

        User(String id, String name) { this.id = id; this.name = name; }
        public String toString() { return "User{id=" + id + ", name=" + name + "}"; }
    }

    static class Device {
        final String deviceId;
        final String status;

        Device(String deviceId, String status) { this.deviceId = deviceId; this.status = status; }
        public String toString() { return "Device{id=" + deviceId + ", status=" + status + "}"; }
    }

    // 绑定具体类型：只处理 User，主键 String
    static class UserRepository extends AbstractRepository<User, String> {
        protected String idOf(User u) { return u.id; }
    }

    // 绑定具体类型：只处理 Device，主键 String
    static class DeviceRepository extends AbstractRepository<Device, String> {
        protected String idOf(Device d) { return d.deviceId; }
    }

    public static void main(String[] args) {
        // 同一个基类，两套实体：泛型接口一次定义、任意实体复用
        UserRepository users = new UserRepository();
        users.save(new User("u1", "Alice"));
        users.save(new User("u2", "Bob"));
        System.out.println("用户数: " + users.count());
        System.out.println("查找 u1: " + users.findById("u1").orElse(null));
        users.deleteById("u1");
        System.out.println("删除 u1 后查找: " + users.findById("u1").isPresent() + "，剩余: " + users.findAll());

        DeviceRepository devices = new DeviceRepository();
        devices.save(new Device("d1", "在线"));
        devices.save(new Device("d2", "离线"));
        System.out.println("设备数: " + devices.count());
        System.out.println("查找 d2: " + devices.findById("d2").orElse(null));
    }
}
