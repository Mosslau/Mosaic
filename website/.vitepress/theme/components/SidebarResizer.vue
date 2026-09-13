<script setup>
/**
 * 侧边栏把手：拖拽调宽 + 整栏折叠。
 *
 * 两个实现要点：
 * 1. 把手位置用 `getBoundingClientRect()` 实测侧边栏右缘，而不是复刻 VitePress 的宽度公式
 *    —— 侧边栏在 ≥1440px 断点的宽度是 `calc((100% - (max - 64)) / 2 + var(--vp-sidebar-width) - 32px)`，
 *    自己算容易算漏；实测则任何断点、任何主题改动都自动跟随（折叠后侧边栏被 translateX(-100%)，
 *    rect.right 自然是 0，把手自动落到视口左缘，正好当展开按钮）。
 * 2. 拖拽以「渲染宽度」限幅、把增量施加到 CSS 变量上。这样在 ≥1440px（宽度含 calc 基准）
 *    下依然是直接上手的感觉，且 [200, 440] 的上下限约束的是肉眼看到的宽度。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useData } from 'vitepress'

const KEY_COLLAPSED = 'tenetlang:sidebar-collapsed'
const KEY_WIDTH = 'tenetlang:sidebar-width'
const DEFAULT_WIDTH = 276
const MIN_WIDTH = 200
const MAX_WIDTH = 440
/** 拖拽线宽与半宽：让线的中心正好压在侧边栏右缘上 */
const LINE_W = 14
const HALF = LINE_W / 2
/** 折叠按钮的边长，以及它与分割线之间的间距——与侧边栏分组的折叠箭头（离右边框 16px）取齐 */
const BTN = 22
const GAP = 16

const { page } = useData()
const ready = ref(false)
const hasSidebar = ref(false)
const collapsed = ref(false)
const dragging = ref(false)
/** 拖拽线中心、按钮左缘，单位 px（相对视口） */
const lineX = ref(0)
const btnX = ref(0)
const rendered = ref(DEFAULT_WIDTH)
const grip = ref(null)

const sidebarEl = () => document.querySelector('.VPSidebar')

function currentVar() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--vp-sidebar-width')
  return Number.parseFloat(raw) || DEFAULT_WIDTH
}

function readVar() {
  try {
    const saved = Number.parseInt(localStorage.getItem(KEY_WIDTH) ?? '', 10)
    return Number.isFinite(saved) ? Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, saved)) : DEFAULT_WIDTH
  } catch {
    return DEFAULT_WIDTH
  }
}

function persist(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* 隐私模式下 localStorage 可能不可用，静默降级为不记忆 */
  }
}

/** 重新测量侧边栏右缘，摆放拖拽线与折叠按钮 */
function measure() {
  const el = sidebarEl()
  hasSidebar.value = !!el && getComputedStyle(el).display !== 'none'
  if (!el) return
  // 折叠时不做测量：侧边栏正处在 translateX(-100%) 的过渡中，此刻量到的可能还是旧位置，
  // 而这两个值是 JS 算好的一次性内联值、不会自己跟着动画更新。直接钉到视口左缘。
  if (collapsed.value) {
    lineX.value = 0
    btnX.value = GAP
    return
  }
  // 展开态正常测量；rect.right 已包含 transform，任何断点都自动跟随
  const right = Math.round(el.getBoundingClientRect().right)
  lineX.value = right
  // 按钮整体落在侧边栏内侧，右缘距分割线 GAP，与分组折叠箭头的位置一致
  btnX.value = Math.max(0, right - GAP - BTN)
  rendered.value = Math.round(el.getBoundingClientRect().width)
}

function applyCollapsed(next) {
  collapsed.value = next
  document.documentElement.classList.toggle('sidebar-collapsed', next)
  persist(KEY_COLLAPSED, next ? '1' : '0')
  // 侧边栏有 0.25s 的位移动画，等它落位后再测一次
  window.setTimeout(measure, 300)
}

function applyWidth(px) {
  const clamped = Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, px)))
  document.documentElement.style.setProperty('--vp-sidebar-width', `${clamped}px`)
  persist(KEY_WIDTH, String(clamped))
}

/* ------------------------------------------------------------------ 拖拽 */

let startX = 0
let startRendered = 0
let startVar = 0

function onPointerDown(event) {
  if (collapsed.value) return
  const el = sidebarEl()
  if (!el) return
  startX = event.clientX
  startRendered = el.getBoundingClientRect().width
  startVar = currentVar()
  dragging.value = true
  try {
    grip.value?.setPointerCapture(event.pointerId)
  } catch {
    /* 合成事件（自动化测试）没有真实指针，忽略即可，拖拽逻辑不依赖捕获 */
  }
  event.preventDefault()
}

function onPointerMove(event) {
  if (!dragging.value) return
  const target = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startRendered + (event.clientX - startX)))
  applyWidth(startVar + (target - startRendered))
}

function onPointerUp(event) {
  if (!dragging.value) return
  dragging.value = false
  grip.value?.releasePointerCapture?.(event.pointerId)
  measure()
}

function onKeydown(event) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  const step = (event.shiftKey ? 32 : 8) * (event.key === 'ArrowLeft' ? -1 : 1)
  applyWidth(currentVar() + step)
  window.setTimeout(measure, 0)
}

/* ---------------------------------------------------------------- 生命周期 */

let observer

onMounted(() => {
  try {
    collapsed.value = localStorage.getItem(KEY_COLLAPSED) === '1'
  } catch {
    /* ignore */
  }
  document.documentElement.classList.toggle('sidebar-collapsed', collapsed.value)
  document.documentElement.style.setProperty('--vp-sidebar-width', `${readVar()}px`)

  measure()
  ready.value = true

  window.addEventListener('resize', measure)
  if ('ResizeObserver' in window) {
    observer = new ResizeObserver(() => measure())
    const el = sidebarEl()
    if (el) observer.observe(el)
  }
})

// 客户端路由切换会重建侧边栏（首页没有侧边栏），重新测量
watch(
  () => page.value.relativePath,
  async () => {
    await nextTick()
    window.setTimeout(() => {
      observer?.disconnect()
      const el = sidebarEl()
      if (el && observer) observer.observe(el)
      measure()
    }, 120)
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
  observer?.disconnect()
})
</script>

<template>
  <div
    v-if="ready && hasSidebar"
    class="resizer"
    :class="{ 'is-dragging': dragging, 'is-collapsed': collapsed }"
    :style="{ '--line-x': `${lineX}px`, '--btn-x': `${btnX}px` }"
  >
    <!-- 拖拽区在前、按钮在后：两者都是 fixed 定位，DOM 靠后的命中在上层。
         按钮本身已经移出线的范围，这里只是防御性排序。 -->
    <div
      ref="grip"
      class="resizer__grip"
      role="separator"
      aria-orientation="vertical"
      :aria-label="`调整侧边栏宽度，当前 ${rendered} 像素`"
      :aria-valuenow="rendered"
      :aria-valuemin="MIN_WIDTH"
      :aria-valuemax="MAX_WIDTH"
      tabindex="0"
      title="拖动调整宽度，双击复位；聚焦后可用左右方向键微调"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @dblclick="applyWidth(DEFAULT_WIDTH)"
      @keydown="onKeydown"
    />

    <button
      class="resizer__toggle"
      type="button"
      :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
      :aria-expanded="collapsed ? 'false' : 'true'"
      :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
      @click="applyCollapsed(!collapsed)"
    >
      <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <path
          :d="collapsed ? 'M6 3.5 L10.5 8 L6 12.5' : 'M10 3.5 L5.5 8 L10 12.5'"
          fill="none"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
</template>

<style scoped>
/* 容器只做逻辑包裹：两个子元素各自 fixed 定位，位置由 JS 写入的变量决定 */
.resizer {
  pointer-events: none;
}

/* 拖拽细线：中心压在侧边栏右缘上 */
.resizer__grip {
  position: fixed;
  top: calc(var(--vp-nav-height) + 8px);
  bottom: 8px;
  left: var(--line-x, 0px);
  width: 14px;
  margin-left: -7px;
  /* 夹在侧边栏（--vp-z-index-sidebar: 25）与导航（--vp-z-index-nav: 30）之间 */
  z-index: 28;
  cursor: col-resize;
  pointer-events: auto;
  touch-action: none;
}

/* 常态只画一条 1px 细线，与图纸的其余分隔线同族 */
.resizer__grip::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
  background: var(--t-rule);
  transition: width var(--t-dur) var(--t-ease), background var(--t-dur) var(--t-ease);
}

.resizer:hover .resizer__grip::after,
.resizer.is-dragging .resizer__grip::after,
.resizer__grip:focus-visible::after {
  width: 2px;
  background: var(--vp-c-brand-2);
}

.resizer__grip:focus-visible {
  outline: none;
}

/* 折叠按钮：整体落在侧边栏内侧、右缘距分割线 16px，
   与侧边栏分组的折叠箭头同一个内缩位置，不再骑在线上 */
.resizer__toggle {
  position: fixed;
  top: calc(var(--vp-nav-height) + 10px);
  left: var(--btn-x, 0px);
  z-index: 29;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  padding: 0;
  /* 边框用 ink-3 而非 rule-strong：后者在深色下对按钮底色只有 2.0:1，
     低于 WCAG 1.4.11 对 UI 边界要求的 3:1；ink-3 两种模式分别是 5.0 / 5.5:1 */
  border: var(--t-hair) solid var(--t-ink-3);
  border-radius: var(--t-radius);
  background: var(--t-surface);
  color: var(--t-ink-2);
  cursor: pointer;
  pointer-events: auto;
  opacity: 0;
  transition: opacity var(--t-dur) var(--t-ease), color var(--t-dur) var(--t-ease),
    border-color var(--t-dur) var(--t-ease);
}

/* 折叠后按钮是唯一的展开入口，常驻显示；展开时悬停/聚焦才出现，不打扰阅读 */
.resizer:hover .resizer__toggle,
.resizer.is-collapsed .resizer__toggle,
.resizer__toggle:focus-visible {
  opacity: 1;
}

/* 折叠态用品牌色点明「可点」，否则深色底上这个按钮几乎看不见 */
.resizer.is-collapsed .resizer__toggle,
.resizer__toggle:hover,
.resizer__toggle:focus-visible {
  color: var(--vp-c-brand-1);
  border-color: var(--vp-c-brand-2);
}

@media (prefers-reduced-motion: reduce) {
  .resizer__grip::after,
  .resizer__toggle {
    transition: none;
  }
}

/* <960px 时侧边栏是汉堡抽屉，没有可拖拽的常驻栏 */
@media (max-width: 959px) {
  .resizer {
    display: none;
  }
}
</style>
