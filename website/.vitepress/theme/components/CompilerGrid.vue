<script setup>
import curriculum from '../../data/curriculum.json'

const tenet = curriculum.tenet
const compilers = tenet.compilers
</script>

<template>
  <section class="section">
    <h2 class="section__head">
      Tenet 的三个编译器
      <span class="section__note">同一套语言设计，自主度依次提高，编译产物逐字节一致</span>
    </h2>

    <a v-if="tenet.design" class="design" :href="tenet.design.link">
      <span class="design__label">完整文档</span>
      <span class="design__title">{{ tenet.design.title }}</span>
      <span class="design__meta">
        设计溯源 / 语言规范 / 架构 / LLVM 后端 / 实现 / 演进 · 约 {{ tenet.design.minutes }} 分钟
      </span>
    </a>

    <ul class="lattice lattice--compilers">
      <li v-for="compiler in compilers" :key="compiler.slug">
        <a class="cc" :href="compiler.link">
          <span class="cc__name">compiler-{{ compiler.slug }}</span>
          <span class="cc__row">
            <span class="cc__key">前端</span>
            <span class="cc__val">{{ compiler.frontend }}</span>
          </span>
          <span class="cc__row">
            <span class="cc__key">后端</span>
            <span class="cc__val">{{ compiler.backend }}</span>
          </span>
          <span class="cc__tests">{{ compiler.tests }} 项测试</span>
        </a>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.design {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 14px;
  margin-bottom: 22px;
  padding: 15px 18px;
  border: var(--t-hair) solid var(--t-rule);
  border-left: 2px solid var(--vp-c-brand-2);
  border-radius: var(--t-radius);
  text-decoration: none;
  background: var(--t-surface);
  transition: background var(--t-dur) var(--t-ease);
}

.design:hover,
.design:focus-visible {
  background: var(--t-surface-sunken);
}

.design__label {
  font-size: 12.5px;
  color: var(--t-ink-3);
}

.design__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--t-ink);
}

.design__meta {
  font-size: 12.5px;
  color: var(--t-ink-3);
}

.cc {
  display: grid;
  gap: 9px;
  height: 100%;
  padding: 22px 22px 20px;
  text-decoration: none;
  transition: background var(--t-dur) var(--t-ease);
}

.cc:hover,
.cc:focus-visible {
  background: var(--t-surface-sunken);
}

.cc__name {
  font-family: var(--vp-font-family-mono);
  font-size: 15px;
  font-weight: 600;
  color: var(--t-ink);
}

.cc__row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  font-size: 13px;
  line-height: 1.65;
}

.cc__key {
  color: var(--t-ink-3);
}

.cc__val {
  color: var(--t-ink-2);
}

.cc__tests {
  margin-top: auto;
  padding-top: 12px;
  border-top: var(--t-hair) solid var(--t-rule);
  font-family: var(--vp-font-family-mono);
  font-size: 12px;
  color: var(--t-ink-3);
}
</style>
