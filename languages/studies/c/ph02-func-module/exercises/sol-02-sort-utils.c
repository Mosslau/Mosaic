/* exercises/sol-02-sort-utils.c —— 数组排序工具库参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-02-sort-utils.c -o sol02
 * 运行：./sol02
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

void bubble_sort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - 1 - i; j++) {
            if (arr[j] > arr[j + 1]) {
                int t = arr[j]; arr[j] = arr[j + 1]; arr[j + 1] = t;
            }
        }
    }
}

void select_sort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        int min_idx = i;
        for (int j = i + 1; j < n; j++) {
            if (arr[j] < arr[min_idx]) min_idx = j;
        }
        int t = arr[i]; arr[i] = arr[min_idx]; arr[min_idx] = t;
    }
}

static void print_arr(const char *label, const int arr[], int n) {
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("\n");
}

int main(void) {
    int a[] = {5, 2, 8, 1, 9};
    int b[] = {5, 2, 8, 1, 9};
    int n = 5;

    bubble_sort(a, n);
    print_arr("bubble_sort", a, n);

    select_sort(b, n);
    print_arr("select_sort", b, n);
    return 0;
}
