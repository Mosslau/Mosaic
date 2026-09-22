/* driver_test.c —— C 驱动测试：确定性操作序列 + 错误路径断言
 * 验证环境：clang（Apple clang 21.0.0，C11）
 * 验证状态：已验证（make test 退出码 0）
 * 数据（dim=3）：id=100 v=(1,0,0)；id=200 v=(0,1,0)；id=300 v=(0,0,1)；id=400 v=(1,1,0)
 * 查询 q=(0.9,0.1,0)，平方 L2 距离：100→0.02、400→0.82、200→1.62、300→1.82，
 * 升序 top3 = [100, 400, 200]。Python 驱动用同一份数据，两侧互证。
 */
#include "vec_index_api.h"

#include <stdio.h>

static const float k_a[3] = {1.0f, 0.0f, 0.0f};
static const float k_b[3] = {0.0f, 1.0f, 0.0f};
static const float k_c[3] = {0.0f, 0.0f, 1.0f};
static const float k_d[3] = {1.0f, 1.0f, 0.0f};
static const float k_q[3] = {0.9f, 0.1f, 0.0f};

int main(void) {
    int fails = 0;

    /* 版本检查先行 */
    if (vec_index_version() < 1) {
        fprintf(stderr, "[FAIL] version\n");
        return 1;
    }
    /* 非法 dim：create 返回 NULL */
    if (vec_index_create(0) != NULL) {
        fprintf(stderr, "[FAIL] create(dim=0) should return NULL\n");
        ++fails;
    }
    vec_index* idx = vec_index_create(3);
    if (idx == NULL) {
        fprintf(stderr, "[FAIL] create\n");
        return 1;
    }

    /* 正常 add ×4 + 错误路径（维度错 / 空指针） */
    if (vec_index_add(idx, 100, k_a, 3) != VI_OK) { fprintf(stderr, "[FAIL] add 100\n"); ++fails; }
    if (vec_index_add(idx, 200, k_b, 3) != VI_OK) { fprintf(stderr, "[FAIL] add 200\n"); ++fails; }
    if (vec_index_add(idx, 300, k_c, 3) != VI_OK) { fprintf(stderr, "[FAIL] add 300\n"); ++fails; }
    if (vec_index_add(idx, 400, k_d, 3) != VI_OK) { fprintf(stderr, "[FAIL] add 400\n"); ++fails; }
    if (vec_index_add(idx, 500, k_a, 2) != VI_ERR_DIM) { fprintf(stderr, "[FAIL] add dim err\n"); ++fails; }
    if (vec_index_add(NULL, 100, k_a, 3) != VI_ERR_NULL) { fprintf(stderr, "[FAIL] add null\n"); ++fails; }

    int64_t n = 0;
    if (vec_index_size(idx, &n) != VI_OK || n != 4) { fprintf(stderr, "[FAIL] size\n"); ++fails; }

    /* search top3：期望 id 序 [100, 400, 200]，距离 0.02 / 0.82 / 1.62 */
    vec_hit hits[3];
    int64_t count = 0;
    if (vec_index_search(idx, k_q, 3, 3, hits, 3, &count) != VI_OK || count != 3) {
        fprintf(stderr, "[FAIL] search\n");
        ++fails;
    } else {
        const int64_t want_ids[3] = {100, 400, 200};
        const float want_dists[3] = {0.02f, 0.82f, 1.62f};
        for (int i = 0; i < 3; ++i) {
            if (hits[i].id != want_ids[i] || hits[i].dist > want_dists[i] + 1e-4f ||
                hits[i].dist < want_dists[i] - 1e-4f) {
                fprintf(stderr, "[FAIL] hit[%d] id=%lld dist=%.3f\n", i,
                        (long long)hits[i].id, (double)hits[i].dist);
                ++fails;
            }
        }
    }

    /* 错误路径：cap<topk、query 维度错、空索引 search、空指针 */
    if (vec_index_search(idx, k_q, 3, 5, hits, 3, &count) != VI_ERR_CAP) {
        fprintf(stderr, "[FAIL] cap err\n"); ++fails;
    }
    if (vec_index_search(idx, k_q, 2, 3, hits, 3, &count) != VI_ERR_DIM) {
        fprintf(stderr, "[FAIL] dim err\n"); ++fails;
    }
    vec_index* empty = vec_index_create(3);
    if (vec_index_search(empty, k_q, 3, 1, hits, 1, &count) != VI_ERR_EMPTY) {
        fprintf(stderr, "[FAIL] empty err\n"); ++fails;
    }
    if (vec_index_search(NULL, k_q, 3, 1, hits, 1, &count) != VI_ERR_NULL) {
        fprintf(stderr, "[FAIL] null err\n"); ++fails;
    }
    vec_index_destroy(empty);
    vec_index_destroy(idx);

    if (fails == 0) {
        printf("[PASS] C driver: top3 = [100, 400, 200], all error paths OK\n");
        return 0;
    }
    return 1;
}
