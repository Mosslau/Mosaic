<script setup>
import curriculum from '../../data/curriculum.json'

const total = curriculum.stats.languageDocs + curriculum.stats.analysisDocs + curriculum.stats.tenetDocs

const paths = [
  {
    mark: '学',
    title: '语言学习笔记',
    question: '这门语言有什么、怎么学',
    detail: `${curriculum.stats.languages} 门语言，${curriculum.stats.chapters} 个编号阶段，${curriculum.stats.languageDocs} 篇文档`,
    link: '/studies/',
  },
  {
    mark: '析',
    title: '语言设计分析',
    question: '它为什么这么设计、代价是什么',
    detail: `${curriculum.analysis.length} 个分析台，${curriculum.stats.analysisDocs} 篇笔记，每篇配一个可运行 demo`,
    link: '/analysis/',
  },
  {
    mark: '合',
    title: 'Tenet 语言与编译器',
    question: '吸收了哪些优点、合成出什么',
    detail: `${curriculum.tenet.compilers.length} 个自主度不同的编译器实现，编译产物逐字节一致`,
    link: '/tenet/',
  },
]
</script>

<template>
  <section class="paths">
    <h2 class="paths__head">
      三条主线，一条路线
      <span class="paths__note">先学一门语言 → 再看它的设计取舍 → 最后看这些设计如何被合成与实现</span>
    </h2>

    <ol class="paths__list">
      <li v-for="path in paths" :key="path.mark" class="path">
        <a class="path__hit" :href="path.link">
          <span class="path__mark" aria-hidden="true">{{ path.mark }}</span>
          <span class="path__title">{{ path.title }}</span>
          <span class="path__question">{{ path.question }}</span>
          <span class="path__detail">{{ path.detail }}</span>
        </a>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.paths {
  margin-top: 76px;
}

.paths__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 16px;
  margin: 0 0 22px;
  font-size: 19px;
  font-weight: 600;
  color: var(--t-ink);
}

.paths__note {
  font-size: 13.5px;
  font-weight: 400;
  color: var(--t-ink-3);
}

.paths__list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: var(--t-hair) solid var(--t-rule);
  border-bottom: var(--t-hair) solid var(--t-rule);
}

.path {
  border-left: var(--t-hair) solid var(--t-rule);
}

.path:first-child {
  border-left: 0;
}

.path__hit {
  display: grid;
  gap: 7px;
  padding: 26px 26px 28px;
  text-decoration: none;
  transition: background var(--t-dur) var(--t-ease);
}

.path:hover .path__hit,
.path__hit:focus-visible {
  background: var(--t-surface-sunken);
}

.path__mark {
  font-size: 26px;
  font-weight: 600;
  line-height: 1;
  color: var(--t-ink-3);
}

.path__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--t-ink);
}

.path__question {
  font-size: 14px;
  color: var(--t-ink-2);
}

.path__detail {
  margin-top: 4px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--t-ink-3);
}

@media (max-width: 780px) {
  .paths__list {
    grid-template-columns: minmax(0, 1fr);
  }

  .path {
    border-left: 0;
    border-top: var(--t-hair) solid var(--t-rule);
  }

  .path:first-child {
    border-top: 0;
  }
}
</style>
