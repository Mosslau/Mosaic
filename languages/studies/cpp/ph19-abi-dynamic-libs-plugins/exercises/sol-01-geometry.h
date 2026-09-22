// exercises/sol-01-geometry.h —— 练习 1 共享头（C 与 C++ 双编译器可用）
#ifndef PH19_SOL01_GEOMETRY_H
#define PH19_SOL01_GEOMETRY_H

#ifdef __cplusplus
extern "C" {
#endif

// C ABI 公共接口：矩形几何（单位制自定，本练习只关心数值）
double rect_area(double w, double h);
double rect_perimeter(double w, double h);
int rect_api_version(void);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // PH19_SOL01_GEOMETRY_H
