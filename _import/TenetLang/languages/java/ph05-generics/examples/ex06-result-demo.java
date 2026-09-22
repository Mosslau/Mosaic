// examples/ex06-result-demo.java —— 泛型 Result 封装：成功/失败统一 + map 变换
// 对应主文档「6. 代码示例 / 示例 6」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex06-result-demo.java
// 运行：java ResultDemo
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.function.Function;

class ResultDemo {
    static class Result<T> {
        private final T data;
        private final String error;

        private Result(T d, String e) { data = d; error = e; }
        public static <T> Result<T> success(T data) { return new Result<>(data, null); }
        public static <T> Result<T> failure(String error) { return new Result<>(null, error); }
        public boolean isSuccess() { return error == null; }
        public T getData() {
            if (error != null) throw new IllegalStateException("失败: " + error);
            return data;
        }

        // map 保持成败语义不变：失败时原样传递错误，成功时才应用函数
        public <U> Result<U> map(Function<T, U> f) {
            return isSuccess() ? success(f.apply(data)) : failure(error);
        }

        public String toString() { return isSuccess() ? "Success(" + data + ")" : "Failure(" + error + ")"; }
    }

    static Result<String> getDeviceStatus(String id) {
        if (id == null || id.isEmpty()) return Result.failure("设备ID不能为空");
        if (id.startsWith("err")) return Result.failure("设备不存在: " + id);
        return Result.success("在线");
    }

    public static void main(String[] args) {
        System.out.println("device-001: " + getDeviceStatus("device-001"));
        System.out.println("err-device: " + getDeviceStatus("err-device"));
        System.out.println("空ID:     " + getDeviceStatus(""));
        System.out.println("map 后:   " + getDeviceStatus("device-001").map(String::length));
    }
}
