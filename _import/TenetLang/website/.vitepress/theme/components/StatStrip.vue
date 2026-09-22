<script setup>
import { computed } from 'vue'
import curriculum from '../../data/curriculum.json'

const stats = curriculum.stats

const items = computed(() => [
  { value: stats.languages, label: '门语言' },
  { value: stats.chapters, label: '个编号阶段' },
  {
    value: stats.languageDocs + stats.analysisDocs + stats.tenetDocs,
    label: '篇收录文档',
  },
  { value: stats.analysisDocs, label: '篇设计分析' },
  { value: curriculum.tenet.compilers.length, label: '个编译器实现' },
])
</script>

<template>
  <dl class="strip">
    <div v-for="item in items" :key="item.label" class="strip__cell">
      <dt class="strip__value">{{ item.value }}</dt>
      <dd class="strip__label">{{ item.label }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 56px 0 0;
  border-top: var(--t-hair) solid var(--t-rule);
  border-bottom: var(--t-hair) solid var(--t-rule);
}

.strip__cell {
  padding: 18px 20px 16px;
  border-left: var(--t-hair) solid var(--t-rule);
}

.strip__cell:first-child {
  border-left: 0;
  padding-left: 0;
}

.strip__value {
  font-family: var(--vp-font-family-mono);
  font-size: 28px;
  font-weight: 500;
  line-height: 1.1;
  color: var(--t-ink);
  font-variant-numeric: tabular-nums;
}

.strip__label {
  margin: 5px 0 0;
  font-size: 13px;
  color: var(--t-ink-3);
}

@media (max-width: 720px) {
  .strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .strip__cell {
    border-top: var(--t-hair) solid var(--t-rule);
    padding-left: 16px;
  }

  .strip__cell:nth-child(odd) {
    border-left: 0;
    padding-left: 0;
  }

  .strip__cell:nth-child(-n + 2) {
    border-top: 0;
  }
}
</style>
