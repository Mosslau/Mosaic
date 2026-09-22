<script setup>
import curriculum from '../../data/curriculum.json'

defineProps({
  heading: { type: Boolean, default: true },
})

const languages = curriculum.languages

const totalMinutes = (lang) => lang.chapters.reduce((sum, chapter) => sum + (chapter.minutes || 0), 0)
const hours = (lang) => Math.max(1, Math.round(totalMinutes(lang) / 60))
</script>

<template>
  <section class="section">
    <h2 v-if="heading" class="section__head">
      六门语言
      <span class="section__note">每门一条 Roadmap，附示例、练习与阶段项目</span>
    </h2>

    <ul class="lattice">
      <li v-for="lang in languages" :key="lang.id">
        <a class="lang" :href="lang.board" :style="{ '--accent': `var(--t-${lang.token})` }">
          <span class="lang__name">{{ lang.name }}</span>
          <span class="lang__tagline">{{ lang.tagline }}</span>
          <span class="lang__stats">
            <span class="lang__stat"><b>{{ lang.chapters.length }}</b> 阶段</span>
            <span class="lang__stat"><b>{{ lang.docs }}</b> 篇文档</span>
            <span class="lang__stat">约 <b>{{ hours(lang) }}</b> 小时</span>
          </span>
        </a>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.lang {
  display: grid;
  gap: 10px;
  height: 100%;
  padding: 24px 24px 22px;
  text-decoration: none;
  transition: background var(--t-dur) var(--t-ease);
}

.lang:hover,
.lang:focus-visible {
  background: color-mix(in srgb, var(--accent) 7%, var(--t-surface));
}

.lang__name {
  font-family: var(--vp-font-family-mono);
  font-size: 25px;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--accent);
}

.lang__tagline {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--t-ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.lang__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: auto;
  padding-top: 14px;
  border-top: var(--t-hair) solid var(--t-rule);
  font-size: 12.5px;
  color: var(--t-ink-3);
}

.lang__stat b {
  font-family: var(--vp-font-family-mono);
  font-weight: 500;
  color: var(--t-ink-2);
  font-variant-numeric: tabular-nums;
}
</style>
