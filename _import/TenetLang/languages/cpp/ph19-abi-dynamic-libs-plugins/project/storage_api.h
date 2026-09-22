// project/storage_api.h —— C ABI 存储引擎插件接口（C 与 C++ 双编译器可用）
// 教学点：插件边界的「稳定接口」长什么样——全部是 C 链接、函数指针表 +
// opaque 句柄 + 显式错误码 + 生命周期注释。头文件即契约：宿主与每个插件
// 都 include 它，但运行期靠 dlopen 相遇，契约只由本文档 + 版本号维持。
//
// 设计要点：
//   · struct storage_engine 只前向声明：宿主持有 opaque 句柄，不能 delete、
//     不能碰内部成员（编译期护栏）；真正内存由引擎的 create/destroy 管理。
//   · 能力用错误码表达而不是宿主去猜名字：del 对 file 后端返回
//     ENGINE_ERR_UNSUPPORTED，宿主把「能力探测」当第一类流程。
//   · 字符串生命周期：get/describe 返回的 const char* 只有效到**下一次**
//     引擎调用前（本 demo 约定）——跨 ABI 边界没法返回 std::string，
//     裸指针 + 生命周期注释是唯一选择，宿主必须在约定窗口内消费。
#ifndef PH19_PROJECT_STORAGE_API_H
#define PH19_PROJECT_STORAGE_API_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct storage_engine storage_engine;  // opaque：实现细节在插件那一侧

enum {
    ENGINE_OK = 0,
    ENGINE_ERR_MISSING = -1,     // key 不存在
    ENGINE_ERR_UNSUPPORTED = -2, // 本后端不支持该操作（能力差异）
    ENGINE_ERR_IO = -3           // 底层 IO 失败（file 后端写文件失败等）
};

// 引擎功能表：每个插件实例化一份并导出。函数指针 + 数据（版本号）
// 都在结构体里，宿主一次 dlsym("engine_get_api") 拿到整张表。
typedef struct engine_api {
    int api_major;  // 接口版本：major 变 = 结构/语义断裂，宿主必须拒绝
    int api_minor;  // major 不变时 minor 只增（尾部追加式演进）

    storage_engine* (*create)(const char* config);  // config：后端参数（路径等），可为 NULL
    void (*destroy)(storage_engine* engine);        // 谁创建谁销毁：引擎侧释放

    int (*put)(storage_engine* engine, const char* key, const char* value);
    const char* (*get)(storage_engine* engine, const char* key);  // NULL=不存在；见文件头生命周期注释
    int (*del)(storage_engine* engine, const char* key);
    const char* (*describe)(storage_engine* engine);  // 人类可读的后端描述
} engine_api;

/* 每个插件必须导出的唯一入口：返回本插件的引擎功能表 */
extern const engine_api* engine_get_api(void);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // PH19_PROJECT_STORAGE_API_H
