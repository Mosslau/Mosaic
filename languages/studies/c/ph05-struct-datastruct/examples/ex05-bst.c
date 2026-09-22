// 来源：05-struct-datastruct.md 第 6 章示例 5 —— 二叉搜索树 BST（有序字典）
// 设计要点：递归释放必须后序（先子后父），否则 free 父节点后左右指针悬空
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex05-bst.c -o ex05-bst
// 运行：./ex05-bst
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct BSTNode {
    int             key;
    struct BSTNode *left, *right;
} BSTNode;

BSTNode *bst_insert(BSTNode *root, int key) {
    if (root == NULL) {
        BSTNode *n = malloc(sizeof(BSTNode));
        if (n == NULL) return NULL;
        n->key = key; n->left = n->right = NULL;
        return n;
    }
    if (key < root->key)      root->left  = bst_insert(root->left, key);
    else if (key > root->key) root->right = bst_insert(root->right, key);
    return root;                    /* 相等则忽略（无重复键） */
}

BSTNode *bst_find(BSTNode *root, int key) {
    while (root != NULL) {
        if (key < root->key)      root = root->left;
        else if (key > root->key) root = root->right;
        else                      return root;
    }
    return NULL;
}

void bst_inorder(BSTNode *root) {           /* 中序遍历 = 有序输出 */
    if (root == NULL) return;
    bst_inorder(root->left);
    printf("%d ", root->key);
    bst_inorder(root->right);
}

void bst_destroy(BSTNode *root) {           /* 后序释放：先子后父 */
    if (root == NULL) return;
    bst_destroy(root->left);
    bst_destroy(root->right);
    free(root);
}

int main(void) {
    BSTNode *root = NULL;
    int keys[] = {50, 30, 70, 20, 40, 60, 80};
    for (int i = 0; i < 7; i++) root = bst_insert(root, keys[i]);

    printf("中序遍历: "); bst_inorder(root); printf("\n");
    printf("查找 40: %s\n", bst_find(root, 40) ? "找到" : "未找到");
    printf("查找 45: %s\n", bst_find(root, 45) ? "找到" : "未找到");
    bst_destroy(root);
    return 0;
}
