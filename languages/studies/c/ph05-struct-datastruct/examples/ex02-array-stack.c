// 来源：05-struct-datastruct.md 第 6 章示例 2 —— 数组栈 + 括号匹配
// 设计要点：数组栈容量固定、无 malloc 开销、缓存友好；括号匹配场景输入长度可预测
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex02-array-stack.c -o ex02-array-stack
// 运行：./ex02-array-stack
// 验证状态：已验证
#include <stdio.h>

#define STACK_MAX 256

typedef struct { char data[STACK_MAX]; int top; } Stack;

void stack_init(Stack *s)      { s->top = -1; }
int  stack_is_empty(Stack *s)  { return s->top == -1; }
int  stack_is_full(Stack *s)   { return s->top == STACK_MAX - 1; }

int stack_push(Stack *s, char c) {
    if (stack_is_full(s)) return -1;
    s->data[++(s->top)] = c;
    return 0;
}

int stack_pop(Stack *s, char *out) {
    if (stack_is_empty(s)) return -1;
    *out = s->data[(s->top)--];
    return 0;
}

/* 括号匹配：返回 1 匹配，0 不匹配 */
int brackets_match(const char *expr) {
    Stack s;
    stack_init(&s);
    for (const char *p = expr; *p != '\0'; p++) {
        switch (*p) {
        case '(': case '[': case '{':
            if (stack_push(&s, *p) != 0) return 0;
            break;
        case ')': case ']': case '}': {
            char open;
            if (stack_pop(&s, &open) != 0) return 0;
            if ((*p == ')' && open != '(') ||
                (*p == ']' && open != '[') ||
                (*p == '}' && open != '{')) return 0;
            break;
        }
        }
    }
    return stack_is_empty(&s);
}

int main(void) {
    const char *tests[] = {"()", "([]){}", "([)]", "((())", "(]"};
    int         expected[] = {1, 1, 0, 0, 0};
    for (int i = 0; i < 5; i++)
        printf("\"%s\"  ->  %s  (预期 %s)\n",
               tests[i],
               brackets_match(tests[i]) ? "匹配" : "不匹配",
               expected[i]         ? "匹配" : "不匹配");
    return 0;
}
