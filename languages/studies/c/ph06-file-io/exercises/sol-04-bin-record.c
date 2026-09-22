// 来源：06-file-io.md 第 6 章示例 4 —— 二进制文件读写结构体（fwrite/fread）
// 参考实现复用自 examples/ex04-bin-record.c（题解分离：题目见 README.md）
// 对应 roadmap 练习"二进制文件读写结构体数据"
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex04-bin-record.c -o ex04-bin-record
// 运行：./ex04-bin-record   （生成 records.bin 后读回；运行产物验证后清理）
// 验证状态：已验证
#include <stdio.h>
typedef struct {
    int    id;        /* 数值 + 定长字符数组, 不含指针 */
    double score;
    char   name[32];
} Record;
static int write_records(const char *path) {
    FILE *fp = fopen(path, "wb");            /* 必须显式二进制模式 */
    if (fp == NULL) { perror(path); return -1; }
    Record data[] = {
        {1, 88.5,  "Alice"},
        {2, 92.0,  "Bob"},
        {3, 79.25, "Carol"},
    };
    size_t n = sizeof(data) / sizeof(data[0]);
    size_t written = fwrite(data, sizeof(Record), n, fp);
    if (written != n) {
        fprintf(stderr, "写入不完整: %zu/%zu\n", written, n);
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}
static int read_records(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) { perror(path); return -1; }
    Record r;
    size_t count = 0;
    while (fread(&r, sizeof(Record), 1, fp) == 1) {   /* 逐条读回 */
        printf("id=%d  name=%-8s  score=%.2f\n", r.id, r.name, r.score);
        count++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return -1; }
    fclose(fp);
    printf("共读回 %zu 条记录 (每条 %zu 字节)\n", count, sizeof(Record));
    return 0;
}
int main(void) {
    const char *path = "records.bin";
    if (write_records(path) != 0) return 1;
    return read_records(path) == 0 ? 0 : 1;
}
