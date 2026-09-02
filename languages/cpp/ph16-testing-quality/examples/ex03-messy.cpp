// examples/ex03-messy.cpp —— clang-format 演示素材：刻意写乱的格式（教学性覆盖）
// 运行前提：本文件是 clang-format 的输入素材，编译运行没问题但格式混乱；
//           修复方式不是自己手改，而是跑 clang-format（见下），产物见 ex03-formatted.cpp。
// 用法（已验证）：
//   clang-format --style=file:ex03.clang-format ex03-messy.cpp > /tmp/ph16cpp-ex03-fmt.cpp
//   diff /tmp/ph16cpp-ex03-fmt.cpp ex03-formatted.cpp   # 应无差异（仓库内已格式化）
//   clang-format --style=file:ex03.clang-format --dry-run --Werror ex03-formatted.cpp  # CI 门禁：零输出
#include <cstdio>
#include <vector>
#include <algorithm>

static int  max_of(const std::vector<int>& v){
int best=v.front();
for(size_t i=1;i<v.size();++i){best=std::max(best,v[i]);}
return best;}

int main(){
const std::vector<int> values{ 3,1,4,1,5,9,2,6 };
std::printf("max=%d\n",max_of(values));
return 0;
}
