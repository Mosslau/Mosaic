<script setup>
import { computed } from 'vue'
import curriculum from '../../data/curriculum.json'

const props = defineProps({
  lang: { type: String, required: true },
})

const pad = (n) => String(n).padStart(2, '0')
const language = computed(() => curriculum.languages.find((item) => item.id === props.lang))

const totalMinutes = computed(() =>
  (language.value?.chapters ?? []).reduce((sum, chapter) => sum + (chapter.minutes || 0), 0),
)
const totalHours = computed(() => Math.max(1, Math.round(totalMinutes.value / 60)))
</script>

<template>
  <div v-if="language" class="board" :style="{ '--accent': `var(--t-${language.token})` }">
    <header class="board__head">
      <h1 class="board__name">{{ language.name }}</h1>
      <p class="board__tagline">{{ language.tagline }}</p>
      <p class="board__stats">
        <span>{{ language.chapters.length }} 个编号阶段</span>
        <span>{{ language.docs }} 篇收录文档</span>
        <span>正文合计约 {{ totalHours }} 小时</span>
      </p>
      <p class="board__links">
        <a class="board__roadmap" :href="language.link">先读学习路线 Roadmap</a>
      </p>
    </header>

    <ol class="lattice lattice--chapters">
      <li v-for="chapter in language.chapters" :key="chapter.n" class="ch">
        <span class="ch__top">
          <span class="ch__n">{{ pad(chapter.n) }}</span>
          <span class="ch__min">约 {{ chapter.minutes }} 分钟</span>
        </span>

        <h3 class="ch__title">
          <a v-if="chapter.link" :href="chapter.link">{{ chapter.title }}</a>
          <template v-else>{{ chapter.title }}</template>
        </h3>

        <p v-if="chapter.goal" class="ch__goal">{{ chapter.goal }}</p>

        <ul v-if="chapter.code && chapter.code.length" class="ch__code">
          <li v-for="layer in chapter.code" :key="layer.label">
            <a :href="layer.link">{{ layer.label }}</a>
          </li>
        </ul>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.board {
  padding-bottom: 24px;
}

/* ------------------------------------------------------------------ 页首 */

.board__head {
  padding: 8px 0 30px;
  border-bottom: var(--t-hair) solid var(--t-rule);
  margin-bottom: 30px;
}

.board__name {
  margin: 0;
  font-family: var(--vp-font-family-mono);
  font-size: clamp(38px, 5vw, 54px);
  font-weight: 600;
  line-height: 1.05;
  letter-spacing: -0.025em;
  color: var(--accent);
  border: 0;
  padding: 0;
}

.board__tagline {
  max-width: 46em;
  margin: 18px 0 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--t-ink-2);
}

.board__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 22px;
  margin: 18px 0 0;
  font-size: 13px;
  color: var(--t-ink-3);
}

.board__links {
  margin: 20px 0 0;
}

.board__roadmap {
  display: inline-block;
  padding: 9px 16px;
  border: var(--t-hair) solid var(--t-rule-strong);
  border-radius: var(--t-radius);
  font-size: 13.5px;
  font-weight: 500;
  color: var(--t-ink);
  text-decoration: none;
  transition: background var(--t-dur) var(--t-ease), border-color var(--t-dur) var(--t-ease);
}

.board__roadmap:hover,
.board__roadmap:focus-visible {
  background: var(--t-surface-sunken);
  border-color: var(--t-ink-3);
}

/* ------------------------------------------------------------------ 卡片 */

.ch {
  display: flex;
  flex-direction: column;
  gap: 9px;
  height: 100%;
  padding: 20px 22px 18px;
  transition: background var(--t-dur) var(--t-ease);
}

.ch:hover {
  background: color-mix(in srgb, var(--accent) 6%, var(--t-surface));
}

.ch__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.ch__n {
  font-family: var(--vp-font-family-mono);
  font-size: 15px;
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

.ch__min {
  font-size: 12px;
  color: var(--t-ink-3);
}

.ch__title {
  margin: 0;
  font-size: 16.5px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--t-ink);
  border: 0;
  padding: 0;
}

/* 标题链接铺满整张卡片，代码层链接再浮到上层 */
.ch__title a {
  color: inherit;
  text-decoration: none;
}

.ch__title a::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
}

.ch__goal {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--t-ink-2);
}

.ch__code {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: auto 0 0;
  padding: 12px 0 0;
  list-style: none;
}

.ch__code a {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 9px;
  border: var(--t-hair) solid var(--t-rule);
  border-radius: var(--t-radius);
  font-size: 12px;
  color: var(--t-ink-2);
  text-decoration: none;
  transition: border-color var(--t-dur) var(--t-ease), color var(--t-dur) var(--t-ease),
    background var(--t-dur) var(--t-ease);
}

.ch__code a:hover,
.ch__code a:focus-visible {
  border-color: var(--accent);
  color: var(--t-ink);
  background: var(--t-surface);
}

.ch__code b {
  font-family: var(--vp-font-family-mono);
  font-weight: 500;
  font-size: 11.5px;
  color: var(--t-ink-3);
  font-variant-numeric: tabular-nums;
}
</style>
