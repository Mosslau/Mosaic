<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import curriculum from '../../data/curriculum.json'

const languages = curriculum.languages
const ROW = 44
const height = languages.length * ROW
const centerY = height / 2

const active = ref(-1)
const settled = ref(false)
let frame = 0

onMounted(() => {
  // 双重 rAF：确保「未划出」这一帧已经真正绘制，否则浏览器会把两次样式合并，动画不触发
  frame = requestAnimationFrame(() => {
    frame = requestAnimationFrame(() => {
      settled.value = true
    })
  })
})

onBeforeUnmount(() => cancelAnimationFrame(frame))

/** 每条导轨从语言所在行出发，弯折汇入最右侧的同一个点 */
function railPath(index) {
  const y = index * ROW + ROW / 2
  const knee = 130 + index * 12
  return `M0,${y} L${knee},${y} C${knee + 60},${y} 210,${centerY} 300,${centerY}`
}

const railClass = (index) => ({
  'is-active': active.value === index,
  'is-dim': active.value !== -1 && active.value !== index,
})
</script>

<template>
  <section class="hero" :class="{ 'is-settled': settled }">
    <h1 class="hero__title">万语归宗</h1>
    <p class="hero__lede">
      六门语言的系统学习路线，它们在设计上各自的取舍，以及由此合成的一门语言与三个编译器。
      下面六条线，是这套知识库的全部入口。
    </p>

    <div class="rig" :style="{ '--row-h': ROW + 'px' }" @mouseleave="active = -1">
      <ul class="rig__labels">
        <li v-for="(lang, index) in languages" :key="lang.id">
          <a
            class="rig__label"
            :href="lang.board"
            :class="railClass(index)"
            :style="{ '--accent': `var(--t-${lang.token})` }"
            @mouseenter="active = index"
            @focus="active = index"
            @blur="active = -1"
          >
            <span class="rig__name">{{ lang.name }}</span>
            <span class="rig__meta">{{ lang.chapters.length }} 阶段</span>
          </a>
        </li>
      </ul>

      <svg
        class="rig__rails"
        :viewBox="`0 0 300 ${height}`"
        :height="height"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <path
          v-for="(lang, index) in languages"
          :key="lang.id"
          :d="railPath(index)"
          :stroke="`var(--t-${lang.token})`"
          :class="railClass(index)"
          :style="{ '--reveal-delay': `${80 * index}ms` }"
          pathLength="1"
          fill="none"
        />
      </svg>

      <a
        class="rig__core"
        href="/tenet/"
        :class="{ 'is-live': active !== -1 }"
        @mouseenter="active = -1"
      >
        <span class="rig__core-bar" aria-hidden="true" />
        <span class="rig__core-name">Tenet</span>
        <span class="rig__core-sub">语言与编译器</span>
      </a>
    </div>
  </section>
</template>

<style scoped>
.hero {
  padding: 72px 0 8px;
}

.hero__title {
  margin: 0;
  font-size: clamp(46px, 7.4vw, 84px);
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: 0.02em;
  color: var(--t-ink);
}

.hero__lede {
  max-width: 34em;
  margin: 22px 0 0;
  font-size: 16px;
  line-height: 1.85;
  color: var(--t-ink-2);
}

/* ------------------------------------------------------------------ 汇流台 */

.rig {
  display: grid;
  grid-template-columns: minmax(148px, 190px) minmax(40px, 1fr) auto;
  align-items: center;
  gap: 0 18px;
  margin-top: 52px;
}

.rig__labels {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-auto-rows: var(--row-h);
}

.rig__label {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 100%;
  padding-left: 16px;
  text-decoration: none;
  color: var(--t-ink-2);
  transition: color var(--t-dur) var(--t-ease), opacity var(--t-dur) var(--t-ease);
}

.rig__label::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 2px;
  background: var(--accent);
  transition: width var(--t-dur) var(--t-ease);
}

.rig__label.is-active,
.rig__label:focus-visible {
  color: var(--t-ink);
}

.rig__label.is-active::before {
  width: 5px;
}

.rig__label.is-dim {
  opacity: 0.42;
}

.rig__name {
  font-family: var(--vp-font-family-mono);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.rig__meta {
  font-size: 12.5px;
  color: var(--t-ink-3);
  font-variant-numeric: tabular-nums;
}

.rig__rails {
  display: block;
  width: 100%;
}

.rig__rails path {
  stroke-width: 1.5;
  opacity: 0.5;
  stroke-dasharray: 1 1;
  stroke-dashoffset: 1;
  /* 错峰只作用于「划出」这一下：延迟挂在 stroke-dashoffset 上，
     hover 的透明度/线宽变化保持即时响应 */
  transition: stroke-dashoffset 900ms var(--t-ease) var(--reveal-delay, 0ms),
    opacity var(--t-dur) var(--t-ease), stroke-width var(--t-dur) var(--t-ease);
}

.hero.is-settled .rig__rails path {
  stroke-dashoffset: 0;
}

.rig__rails path.is-active {
  opacity: 1;
  stroke-width: 3;
}

.rig__rails path.is-dim {
  opacity: 0.16;
}

/* -------------------------------------------------------------- Tenet 节点 */

.rig__core {
  position: relative;
  display: grid;
  gap: 2px;
  min-width: 148px;
  padding: 16px 20px 15px;
  border: var(--t-hair) solid var(--t-rule-strong);
  border-radius: var(--t-radius);
  background: var(--t-surface);
  text-decoration: none;
  transition: border-color var(--t-dur) var(--t-ease), background var(--t-dur) var(--t-ease);
}

.rig__core-bar {
  position: absolute;
  inset: 0 0 auto 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    var(--t-c) 0 16.6%,
    var(--t-cpp) 16.6% 33.2%,
    var(--t-go) 33.2% 49.8%,
    var(--t-java) 49.8% 66.4%,
    var(--t-py) 66.4% 83%,
    var(--t-rs) 83% 100%
  );
}

.rig__core-name {
  font-family: var(--vp-font-family-mono);
  font-size: 19px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--t-ink);
}

.rig__core-sub {
  font-size: 12.5px;
  color: var(--t-ink-3);
}

.rig__core:hover,
.rig__core.is-live {
  border-color: var(--t-ink-3);
  background: var(--t-surface-sunken);
}

/* -------------------------------------------------------------- 窄屏折叠 */

@media (max-width: 860px) {
  .hero {
    padding-top: 44px;
  }

  .rig {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 14px;
    margin-top: 34px;
  }

  .rig__labels {
    display: contents;
  }

  .rig__label {
    height: 46px;
    border: var(--t-hair) solid var(--t-rule);
    border-radius: var(--t-radius);
    background: var(--t-surface);
    padding-left: 14px;
  }

  .rig__rails {
    display: none;
  }

  .rig__core {
    grid-column: 1 / -1;
    margin-top: 4px;
  }
}
</style>
