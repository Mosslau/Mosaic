<script setup>
/**
 * 包一层默认主题的 Layout，只为往 `layout-bottom` 插槽挂侧边栏把手。
 * VitePress 的 Layout 没有暴露侧边栏区域的插槽可用于「栏外」控件（sidebar-nav-* 在栏内，
 * 折叠后就点不到了），所以加在最外层。
 */
import DefaultTheme from 'vitepress/theme'
import SidebarResizer from './SidebarResizer.vue'

const { Layout } = DefaultTheme
</script>

<template>
  <Layout>
    <template #layout-bottom>
      <SidebarResizer />
    </template>
  </Layout>
</template>
